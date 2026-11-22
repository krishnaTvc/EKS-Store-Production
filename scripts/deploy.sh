#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION="${AWS_REGION:-eu-north-1}" ENVIRONMENT="${ENVIRONMENT:-lab}"
export CLUSTER_NAME="${CLUSTER_NAME:-eks-store-${ENVIRONMENT}}"
: "${IMAGE_TAG:?Provide the Git SHA image tag built and pushed to ECR}"
echo "Verifying target EKS cluster '$CLUSTER_NAME' in region '$AWS_REGION'..."
AVAILABLE_CLUSTERS=$(aws eks list-clusters --region "$AWS_REGION" --query "clusters[*]" --output text 2>/dev/null || true)
echo "Existing clusters in $AWS_REGION: [${AVAILABLE_CLUSTERS:-none}]"

if ! aws eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "=========================================================================="
  echo "ERROR: Target EKS cluster '$CLUSTER_NAME' was not found in AWS region '$AWS_REGION'."
  echo "Discovered clusters in region '$AWS_REGION': [${AVAILABLE_CLUSTERS:-none}]"
  echo ""
  echo "If your EKS cluster was deleted or has not yet been provisioned:"
  echo "  1. Go to the 'Actions' tab in GitHub."
  echo "  2. Select 'Terraform Infrastructure Manager' workflow."
  echo "  3. Trigger workflow: stack='platform' (or 'all'), environment='$ENVIRONMENT', action='apply'."
  echo "=========================================================================="
  exit 1
fi
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export CATALOG_ROLE_ARN="${CATALOG_ROLE_ARN:-$(aws iam get-role --role-name "eks-store-catalog-sa-role-${ENVIRONMENT}" --query Role.Arn --output text)}"
export ASSETS_BUCKET="${ASSETS_BUCKET:-eks-store-assets-${ENVIRONMENT}-${ACCOUNT_ID}}"
export FRONTEND_IMAGE="$REGISTRY/eks-store-frontend:$IMAGE_TAG" CATALOG_IMAGE="$REGISTRY/eks-store-catalog:$IMAGE_TAG"
export ORDERS_IMAGE="$REGISTRY/eks-store-orders:$IMAGE_TAG" SEED_IMAGE="$REGISTRY/eks-store-seed:$IMAGE_TAG"
RUN_SUFFIX="${GITHUB_RUN_ID:-$(date +%s)}-${GITHUB_RUN_ATTEMPT:-1}"
export BOOTSTRAP_JOB="eks-store-bootstrap-db-$RUN_SUFFIX" CATALOG_MIGRATION_JOB="eks-store-catalog-migration-$RUN_SUFFIX"
export ORDERS_MIGRATION_JOB="eks-store-orders-migration-$RUN_SUFFIX" SEED_JOB="eks-store-catalog-seed-$RUN_SUFFIX"
python scripts/render_manifests.py
kubectl apply -f .rendered/00-namespace.yaml
kubectl apply -f .rendered/01-serviceaccounts.yaml
kubectl apply -f .rendered/02-configmap.yaml
python scripts/prepare_db_secrets.py
run_job() {
  local file="$1" name="$2"
  kubectl apply -f "$file"
  # Poll both success and failure: do not wait 10 minutes after a known failure.
  for attempt in {1..130}; do
    status=$(kubectl get job "$name" -n eks-store -o json)
    state=$(python -c 'import sys,json; s=json.load(sys.stdin).get("status",{}); print("complete" if s.get("succeeded",0)>0 else "failed" if any(c.get("type")=="Failed" and c.get("status")=="True" for c in s.get("conditions",[])) else "pending")' <<< "$status")
    if [[ "$state" == complete ]]; then
      kubectl logs -n eks-store "job/$name" --all-containers=true --tail=100
      return 0
    fi
    if [[ "$state" == failed ]]; then break; fi
    sleep 5
  done
  kubectl describe job "$name" -n eks-store
  kubectl get pods -n eks-store -l "batch.kubernetes.io/job-name=$name" -o wide
  kubectl logs -n eks-store "job/$name" --all-containers=true --tail=150 || true
  return 1
}
run_job .rendered/jobs/db-bootstrap.yaml "$BOOTSTRAP_JOB"
run_job .rendered/jobs/catalog-migration.yaml "$CATALOG_MIGRATION_JOB"
run_job .rendered/jobs/orders-migration.yaml "$ORDERS_MIGRATION_JOB"
run_job .rendered/jobs/catalog-seed.yaml "$SEED_JOB"
for file in .rendered/0[456]-*.yaml; do kubectl apply -f "$file"; done
kubectl rollout restart deployment/frontend deployment/catalog-service deployment/order-service -n eks-store
for name in frontend catalog-service order-service; do
  kubectl rollout status "deployment/$name" -n eks-store --timeout=600s
done
kubectl get deployment aws-load-balancer-controller -n kube-system >/dev/null
kubectl rollout status deployment/aws-load-balancer-controller -n kube-system --timeout=180s

echo "Discovering and configuring public subnets for AWS Load Balancer Controller..."
VPC_ID=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" --query "cluster.resourcesVpcConfig.vpcId" --output text 2>/dev/null || true)
if [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]]; then
  PUBLIC_SUBNETS=$(aws ec2 describe-subnets --region "$AWS_REGION" \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
    --query "Subnets[*].SubnetId" --output text 2>/dev/null | tr '\t' ',' || true)
  if [[ -z "$PUBLIC_SUBNETS" || "$PUBLIC_SUBNETS" == "None" ]]; then
    PUBLIC_SUBNETS=$(aws ec2 describe-subnets --region "$AWS_REGION" \
      --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=*public*" \
      --query "Subnets[*].SubnetId" --output text 2>/dev/null | tr '\t' ',' || true)
  fi
  if [[ -n "$PUBLIC_SUBNETS" && "$PUBLIC_SUBNETS" != "None" ]]; then
    SUBNET_LIST=$(echo "$PUBLIC_SUBNETS" | tr ',' ' ')
    echo "Ensuring required kubernetes.io/role/elb=1 tag on subnets: $SUBNET_LIST"
    aws ec2 create-tags --region "$AWS_REGION" --resources $SUBNET_LIST --tags Key=kubernetes.io/role/elb,Value=1 || true
    echo "Annotating Ingress with explicit public subnets: $PUBLIC_SUBNETS"
    PUBLIC_SUBNETS="$PUBLIC_SUBNETS" python -c "
import os, yaml
path = '.rendered/07-ingress.yaml'
with open(path) as f: doc = yaml.safe_load(f)
doc.setdefault('metadata', {}).setdefault('annotations', {})['alb.ingress.kubernetes.io/subnets'] = os.environ['PUBLIC_SUBNETS']
with open(path, 'w') as f: yaml.safe_dump(doc, f)
"
  fi
fi

kubectl apply -f .rendered/07-ingress.yaml
