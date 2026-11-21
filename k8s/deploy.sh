#!/usr/bin/env bash
set -e

echo "=== Deploying EKS Store with Native Kubernetes Manifests ==="

# 1. Base infrastructure resources
echo "Applying Namespace..."
kubectl apply -f 00-namespace.yaml

echo "Applying ServiceAccounts..."
kubectl apply -f 01-serviceaccounts.yaml

echo "Applying ConfigMap..."
kubectl apply -f 02-configmap.yaml

echo "Applying SecretProviderClasses..."
kubectl apply -f 03-secretproviderclass.yaml

# 2. Workloads & Routing
echo "Deploying Frontend..."
kubectl apply -f 04-frontend.yaml

echo "Deploying Catalog Service..."
kubectl apply -f 05-catalog.yaml

echo "Deploying Order Service..."
kubectl apply -f 06-orders.yaml

echo "Deploying Ingress..."
kubectl apply -f 07-ingress.yaml

echo ""
echo "=== Core Services & Ingress Deployed Successfully ==="
echo ""

# 3. Optional Database Jobs
if [ "$1" == "--with-jobs" ]; then
  echo "Running Database Bootstrap Job..."
  kubectl delete job eks-store-bootstrap-db -n eks-store --ignore-not-found=true
  kubectl apply -f jobs/db-bootstrap.yaml
  kubectl wait --for=condition=complete job/eks-store-bootstrap-db -n eks-store --timeout=120s || true

  echo "Running Migrations..."
  kubectl delete job eks-store-catalog-migration eks-store-orders-migration -n eks-store --ignore-not-found=true
  kubectl apply -f jobs/catalog-migration.yaml
  kubectl apply -f jobs/orders-migration.yaml
  kubectl wait --for=condition=complete job/eks-store-catalog-migration job/eks-store-orders-migration -n eks-store --timeout=120s || true

  echo "Running Catalog Seed..."
  kubectl delete job eks-store-catalog-seed -n eks-store --ignore-not-found=true
  kubectl apply -f jobs/catalog-seed.yaml
  kubectl wait --for=condition=complete job/eks-store-catalog-seed -n eks-store --timeout=120s || true
fi

echo ""
echo "=== Deployment Status ==="
kubectl get pods -n eks-store -o wide
kubectl get svc -n eks-store
kubectl get ingress -n eks-store
