#!/usr/bin/env bash
set -euo pipefail
CLUSTER_NAME="${CLUSTER_NAME:-eks-store-${ENVIRONMENT:-lab}}"
REGION="${AWS_REGION:-eu-north-1}"

# Attempt to discover cluster version; fallback to default 1.32 if cluster is not reachable
VERSION=$(aws eks describe-cluster --region "$REGION" --name "$CLUSTER_NAME" --query cluster.version --output text 2>/dev/null || echo "1.32")
PATCH=$(curl -fsSL "https://dl.k8s.io/release/stable-${VERSION}.txt" 2>/dev/null || echo "v1.32.2")
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSLo "$TMP_DIR/kubectl" "https://dl.k8s.io/release/${PATCH}/bin/linux/amd64/kubectl"
curl -fsSLo "$TMP_DIR/kubectl.sha256" "https://dl.k8s.io/release/${PATCH}/bin/linux/amd64/kubectl.sha256"
(cd "$TMP_DIR" && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check)
sudo install -m 0755 "$TMP_DIR/kubectl" /usr/local/bin/kubectl
echo "Installed kubectl version ${PATCH}"
