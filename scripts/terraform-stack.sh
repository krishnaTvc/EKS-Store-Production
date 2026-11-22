#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
STACK="${1:?stack required}" ACTION="${2:?plan, apply or destroy required}"
[[ "$STACK" =~ ^(network|data|platform|addons)$ ]] || { echo 'Bootstrap is a separate one-time operation.' >&2; exit 1; }
[[ "$ACTION" =~ ^(plan|apply|destroy)$ ]] || exit 1
export AWS_REGION="${AWS_REGION:-eu-north-1}" ENVIRONMENT="${ENVIRONMENT:-lab}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
STATE_BUCKET="eks-store-tf-state-${ENVIRONMENT}-${ACCOUNT}"
LOCK_TABLE="eks-store-tf-locks-${ENVIRONMENT}"
aws s3api head-bucket --bucket "$STATE_BUCKET"
aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" >/dev/null
terraform -chdir="infra/$STACK" init -input=false \
  -backend-config="bucket=$STATE_BUCKET" -backend-config="key=stacks/$STACK/terraform.tfstate" \
  -backend-config="region=$AWS_REGION" -backend-config="dynamodb_table=$LOCK_TABLE"
ARGS=(-input=false "-var=environment=$ENVIRONMENT" "-var=aws_region=$AWS_REGION")
if [[ "$STACK" == platform || "$STACK" == addons ]]; then ARGS+=("-var=cluster_name=eks-store-$ENVIRONMENT"); fi
if [[ "$ACTION" == apply ]]; then
  terraform -chdir="infra/$STACK" plan "${ARGS[@]}" -out=tfplan
  terraform -chdir="infra/$STACK" apply -input=false tfplan
elif [[ "$ACTION" == destroy ]]; then
  [[ "${CONFIRM_DESTROY:-}" == CONFIRM ]] || { echo 'Set CONFIRM_DESTROY=CONFIRM for destroy.' >&2; exit 1; }
  terraform -chdir="infra/$STACK" destroy -auto-approve "${ARGS[@]}"
else
  terraform -chdir="infra/$STACK" plan "${ARGS[@]}"
fi
