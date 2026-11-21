# Native Kubernetes Manifests for EKS Store

This directory provides clean, standard Kubernetes manifests to deploy the entire EKS Store microservices architecture without Helm.

## Directory Structure
- `00-namespace.yaml`: Defines the `eks-store` namespace.
- `01-serviceaccounts.yaml`: Defines IAM-bound service accounts (`catalog-service-sa`, `order-service-sa`, `frontend-sa`, `db-job-sa`).
- `02-configmap.yaml`: Application environment configuration.
- `03-secretproviderclass.yaml`: AWS Secrets Manager SecretProviderClasses for CSI driver.
- `04-frontend.yaml`: Frontend Deployment & ClusterIP Service.
- `05-catalog.yaml`: Catalog Service Deployment & ClusterIP Service.
- `06-orders.yaml`: Order Service Deployment & ClusterIP Service.
- `07-ingress.yaml`: AWS ALB Ingress configuration.
- `jobs/`: Database bootstrap, Alembic migrations, and catalog seeding jobs.

## Quick Manual Deployment

To deploy all core services and ingress in one step:
```bash
# On Linux/macOS
cd k8s
./deploy.sh

# On Windows PowerShell
cd k8s
.\deploy.ps1
```

Or manually using `kubectl`:
```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-serviceaccounts.yaml
kubectl apply -f k8s/02-configmap.yaml
kubectl apply -f k8s/03-secretproviderclass.yaml
kubectl apply -f k8s/04-frontend.yaml
kubectl apply -f k8s/05-catalog.yaml
kubectl apply -f k8s/06-orders.yaml
kubectl apply -f k8s/07-ingress.yaml
```

To run the database setup jobs:
```bash
kubectl apply -f k8s/jobs/db-bootstrap.yaml
kubectl apply -f k8s/jobs/catalog-migration.yaml
kubectl apply -f k8s/jobs/orders-migration.yaml
kubectl apply -f k8s/jobs/catalog-seed.yaml
```

## Check Public ALB URL
```bash
kubectl get ingress -n eks-store eks-store-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```
