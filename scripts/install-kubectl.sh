#!/usr/bin/env bash
set -euo pipefail
CLUSTER_NAME="${CLUSTER_NAME:-eks-store-${ENVIRONMENT:-lab}}"
VERSION=$(aws eks describe-cluster --region "${AWS_REGION:-eu-north-1}" --name "$CLUSTER_NAME" --query cluster.version --output text)
PATCH=$(curl -fsSL "https://dl.k8s.io/release/stable-${VERSION}.txt")
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSLo "$TMP_DIR/kubectl" "https://dl.k8s.io/release/${PATCH}/bin/linux/amd64/kubectl"
curl -fsSLo "$TMP_DIR/kubectl.sha256" "https://dl.k8s.io/release/${PATCH}/bin/linux/amd64/kubectl.sha256"
(cd "$TMP_DIR" && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check)
sudo install -m 0755 "$TMP_DIR/kubectl" /usr/local/bin/kubectl
