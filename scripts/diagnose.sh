#!/usr/bin/env bash
set +e
echo "=== AWS STS IDENTITY ==="
aws sts get-caller-identity || true
echo "=== EKS CLUSTERS (${AWS_REGION:-eu-north-1}) ==="
aws eks list-clusters --region "${AWS_REGION:-eu-north-1}" || true
echo "=== KUBERNETES RESOURCES ==="
kubectl get pods,deploy,svc,ingress,jobs -n eks-store -o wide
kubectl get events -n eks-store --sort-by=.metadata.creationTimestamp
kubectl describe jobs -n eks-store
kubectl describe pods -n eks-store
for job in $(kubectl get jobs -n eks-store -o jsonpath='{.items[*].metadata.name}'); do
  kubectl logs -n eks-store "job/$job" --all-containers=true --tail=100
done
for name in catalog-service order-service frontend; do
  kubectl logs -n eks-store "deployment/$name" --all-containers=true --tail=100
done
exit 0
