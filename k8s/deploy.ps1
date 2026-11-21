# PowerShell deployment script for EKS Store
$ErrorActionPreference = "Stop"

Write-Host "=== Deploying EKS Store with Native Kubernetes Manifests ===" -ForegroundColor Cyan

Write-Host "Applying Namespace..."
kubectl apply -f 00-namespace.yaml

Write-Host "Applying ServiceAccounts..."
kubectl apply -f 01-serviceaccounts.yaml

Write-Host "Applying ConfigMap..."
kubectl apply -f 02-configmap.yaml

Write-Host "Applying SecretProviderClasses..."
kubectl apply -f 03-secretproviderclass.yaml

Write-Host "Deploying Frontend..."
kubectl apply -f 04-frontend.yaml

Write-Host "Deploying Catalog Service..."
kubectl apply -f 05-catalog.yaml

Write-Host "Deploying Order Service..."
kubectl apply -f 06-orders.yaml

Write-Host "Deploying Ingress..."
kubectl apply -f 07-ingress.yaml

Write-Host "`n=== Core Services & Ingress Deployed Successfully ===" -ForegroundColor Green
kubectl get pods -n eks-store -o wide
kubectl get svc -n eks-store
kubectl get ingress -n eks-store
