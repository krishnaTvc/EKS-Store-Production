# Operations Runbook: EKS Beverage Store

This runbook documents operational procedures, disaster recovery workflows, diagnostic checklists, and cost-control mechanisms for the **EKS Beverage Store** platform.

---

## 1. Quick Diagnostic Checklist

When investigating an issue, follow this ordered boundary verification sequence:
1. **ALB / Ingress Boundary**: Is the ALB healthy and routing traffic to worker nodes?
2. **Pod Scheduling Boundary**: Are pods in `Running` state or `Pending` / `CrashLoopBackOff`?
3. **Database Boundary**: Are connection pools exhausted or is RDS refusing connections?
4. **IAM / Workload Identity Boundary**: Can pods assume their role and read Secrets Manager or S3?

### Common Diagnostic Commands
```bash
# 1. Authenticate to EKS Cluster
aws eks update-kubeconfig --region eu-north-1 --name eks-store-lab

# 2. Check Pods, Services, and Ingress Status
kubectl get pods,svc,ingress -n eks-store -o wide

# 3. Inspect Cluster Events (sorted by time)
kubectl get events -n eks-store --sort-by=.lastTimestamp

# 4. Describe Pod Failures or Pending Scheduling
kubectl describe pod <POD_NAME> -n eks-store

# 5. Stream Pod Logs across All Containers
kubectl logs <POD_NAME> -n eks-store --all-containers --tail=100 -f

# 6. Check Pre-Deploy Job Logs
kubectl logs job/<JOB_NAME> -n eks-store

# 7. Check Helm Release History & Revisions
helm history eks-store -n eks-store
```

---

## 2. First-Time AWS Deployment Runbook

### Step 1: Provision Bootstrap Infrastructure
Authenticate with an AWS Administrator session and create the persistent remote state and OIDC roles:
```bash
cd infra/bootstrap
terraform init
terraform apply -auto-approve
```
*Outputs: `state_bucket_name`, `dynamodb_table_name`, `github_actions_role_arn`.*

### Step 2: Provision Network & Data Stacks
```bash
# Network stack (VPC, Subnets, Gateways, Security Groups)
cd ../network
terraform init
terraform apply -auto-approve

# Data stack (RDS PostgreSQL, Secrets Manager, S3 Buckets, ECR)
cd ../data
terraform init
terraform apply -auto-approve
```

### Step 3: Build & Publish Container Images
```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com

# Build and push images
docker build -t <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-frontend:latest ./frontend
docker push <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-frontend:latest

docker build -t <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-catalog:latest ./catalog-service
docker push <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-catalog:latest

docker build -t <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-orders:latest ./order-service
docker push <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-orders:latest

docker build -f Dockerfile.seed -t <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-seed:latest .
docker push <ACCOUNT_ID>.dkr.ecr.eu-north-1.amazonaws.com/eks-store-seed:latest
```

### Step 4: Upload Asset Images to Private S3
```bash
python scripts/upload_s3.py --bucket <ASSETS_BUCKET_NAME> --region eu-north-1
```

### Step 5: Provision Platform & Addons Stacks
```bash
cd ../platform
terraform init
terraform apply -auto-approve

cd ../addons
terraform init
terraform apply -auto-approve
```

### Step 6: Deploy Application via Helm
```bash
aws eks update-kubeconfig --region eu-north-1 --name eks-store-lab

helm upgrade --install eks-store ./helm/eks-store \
  --namespace eks-store --create-namespace \
  --values ./helm/eks-store/values.yaml \
  --values ./helm/eks-store/values-lab.yaml \
  --wait --timeout 10m
```

### Step 7: Run Acceptance Smoke Tests
```bash
ALB_URL=$(kubectl get ingress eks-store-ingress -n eks-store -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
python scripts/smoke_test.py --url "http://$ALB_URL"
```

---

## 3. Disaster Recovery & Resilience Demonstrations

### Exercise A: Controlled Rollback of a Failed Release
To demonstrate zero-downtime rollback when a candidate image fails readiness checks:
```bash
# 1. Attempt rollout of a faulty image tag
helm upgrade eks-store ./helm/eks-store \
  -n eks-store \
  --set images.catalog.tag=bad-release-tag \
  --wait --timeout 2m || true

# 2. Verify previous pods continue serving traffic without downtime
kubectl get pods -n eks-store

# 3. Roll back to the previous working release
helm rollback eks-store 0 -n eks-store

# 4. Confirm healthy status
kubectl rollout status deployment/catalog-service -n eks-store
```

### Exercise B: Disposable Cluster Recreation (Order Persistence Test)
This exercise proves that **EKS is treated as disposable compute** while RDS preserves order records.
1. Place a real customer order via the UI or `scripts/smoke_test.py` and record the Order UUID (e.g. `550e8400-e29b-41d4-a716-446655440000`).
2. Destroy the EKS platform stack completely:
   ```bash
   cd infra/platform
   terraform destroy -auto-approve
   ```
3. Verify that the RDS PostgreSQL instance in the retained `data` stack is untouched.
4. Recreate the EKS cluster from scratch:
   ```bash
   terraform apply -auto-approve
   cd ../addons && terraform apply -auto-approve
   ```
5. Reinstall the Helm chart:
   ```bash
   helm upgrade --install eks-store ./helm/eks-store -n eks-store --values ./helm/eks-store/values-lab.yaml --wait
   ```
6. Open the UI Track Order modal or execute:
   ```bash
   curl -s http://$ALB_URL/api/orders/550e8400-e29b-41d4-a716-446655440000
   ```
7. **Result**: The order, line items, and price snapshot are intact!

### Exercise C: Amazon RDS Snapshot & Point-in-Time Restore
To test database disaster recovery:
```bash
# 1. Take a manual snapshot of RDS instance
aws rds create-db-snapshot \
  --db-instance-identifier eks-store-rds-lab \
  --db-snapshot-identifier eks-store-backup-manual

# 2. Restore snapshot to a separate recovery instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier eks-store-rds-recovery \
  --db-snapshot-identifier eks-store-backup-manual \
  --db-subnet-group-name eks-store-rds-subnet-group-lab \
  --vpc-security-group-ids <RDS_SG_ID>

# 3. Wait for recovery instance to be available
aws rds wait db-instance-available --db-instance-identifier eks-store-rds-recovery
```

---

## 4. Cost Control & Pausing Strategy

Amazon EKS control plane incurs a fixed hourly charge ($0.10/hour, ~$73/month). Running worker nodes, NAT gateways, and RDS also incur continuous hourly charges.

### Three Pause Levels:

| Level | Action | Retained Resources | What Stops Billing |
|---|---|---|---|
| **Short Pause (Daily)** | Scale node group to 0 nodes. Stop RDS instance. | EKS Control Plane, VPC, NAT Gateway, S3, ECR | EC2 worker node compute, RDS compute |
| **Preferred Long Pause (Recommended)** | Delete Helm app, terminate platform stack (`infra/platform`). Stop or keep RDS. | RDS, S3, ECR, VPC, Subnets, State Backend | EKS Control Plane ($73/mo), EC2 nodes, ALB charges |
| **Archival Pause** | Take final RDS snapshot. Destroy RDS instance and NAT Gateway. | RDS Snapshot, S3 asset bucket, ECR repositories | All active compute, networking, and live database instances |

### Pause Command Execution (via GitHub Actions or CLI):
```bash
# Trigger automated pause workflow via GitHub CLI
gh workflow run environment.yml -f action=pause -f environment=lab -f confirmation=CONFIRM
```
