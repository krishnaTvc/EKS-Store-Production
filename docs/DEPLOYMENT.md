# Deployment and recovery guide

## 1. Scope
This ZIP repairs your current RDS-based repository. It does not silently switch to a PostgreSQL pod. The separate local kind package serves that purpose. No AWS resources were changed while preparing this ZIP, and no live EKS rollout is claimed.

The browser connects to ALB -> Nginx frontend -> catalog/order Services -> private RDS PostgreSQL. Catalog uses its pod IAM role for S3 images. Application images live in ECR.

## 2. Update your existing GitHub repo
Make a backup branch of the current source. Replace its tracked contents with this ZIP (including `.github/`), and commit removed files as removals. Simply copying new files on top without removing old workflows/charts leaves conflicting deployment paths. Do not copy `.terraform/`, state files, `.env` or secrets into GitHub. Do not delete AWS remote state.

The application Helm chart and deployment branch are removed. Existing Terraform-managed addon Helm resources are deliberately retained so your live addon state still has the same resource addresses/providers. Application pods do not use CSI anymore, but its existing addon resources are left alone. Do not uninstall the old application Helm release after applying this edition: its stored ownership could delete resources now managed through kubectl. Stop running the old Helm workflow and reconcile old release metadata separately if needed.

Use your existing `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` GitHub secrets. This release does not assume a GitHub OIDC role. The IAM user needs ECR push, Secrets Manager GetSecretValue, S3 uploads, IAM GetRole and EKS DescribeCluster, plus Kubernetes permissions to manage the app namespace. Custom secret KMS keys additionally require appropriate decrypt permission. Never paste credentials into YAML.

The cluster is explicitly `eks-store-lab` for lab and `eks-store-production` for production. There is no fallback to another discovered cluster. Confirm that your IAM principal has cluster access; use the cluster creator identity or configure a suitable EKS access entry. AWS AdministratorAccess alone does not automatically supply every Kubernetes permission.

## 3. Preserve existing infrastructure and state
Start with source/test validation and the application release if EKS, RDS, ECR, S3 and ALB controller already exist. You do not need a full destroy/recreate.

Terraform workflows initialize existing backends:
- bucket: `eks-store-tf-state-ENVIRONMENT-ACCOUNT`
- lock table: `eks-store-tf-locks-ENVIRONMENT`
- each key: `stacks/STACK/terraform.tfstate`

`all` covers network -> data -> platform -> addons, excluding bootstrap. There is no automatic network cleanup and no automatically generated imports. Use a single-stack plan first to inspect your current state. If AWS objects exist but are absent from state, explicitly import the particular objects using documented identifiers before apply. Use the real secret ARN for Secrets Manager imports. Do not import missing resources; let their resource blocks create them. Existing non-empty ECR repositories must be preserved or imported, not blindly recreated.

Bootstrap remains a separate one-time local operation. Your old workflow already provisioned it, so normally leave it alone. For a truly new account, initialize/apply `infra/bootstrap` locally, configure its existing GitHub-provider option if needed, and preserve the resulting bootstrap state securely. Never recreate bootstrap from empty state on an ephemeral runner.

For planned infrastructure changes, run Terraform Infrastructure Manager with stack, environment and action=plan. Review before action=apply. Platform and addon cluster_name is now explicitly passed. A fresh all-stack plan needs dependencies already present; an ordered apply creates them sequentially. The data stack restores verify-full URLs and makes final RDS snapshot names unique. Review plans carefully; existing passwords and resource addresses are retained, and no password rotation is requested by these changes.

## 4. Secret data contract (one source)
The release reads these AWS Secrets Manager names:

| Secret | Required JSON keys |
|---|---|
| `eks-store/ENVIRONMENT/rds/master` | host, port, master_username, master_password |
| `eks-store/ENVIRONMENT/catalog-db` | host, port, username=catalog_user, password, dbname=catalog; optional DATABASE_URL must agree |
| `eks-store/ENVIRONMENT/order-db` | host, port, username=order_user, password, dbname=orders; optional DATABASE_URL must agree |

Values produced by `infra/data` match this contract. The script validates required fields, consistent endpoints and existing URL/password consistency before writing anything. It reconstructs URLs with correct percent encoding and `sslmode=verify-full`. It never prints secret values. If validation says DATABASE_URL disagrees, fix that AWS source secret deliberately; a restart will not fix inconsistent data. When Terraform manages those values, reconcile through its state/configuration so the next apply does not undo a manual fix.

New Kubernetes Secret names intentionally avoid the old CSI targets:
- `eks-store-bootstrap-db-credentials`: master credentials + both app passwords; used only by bootstrap.
- `eks-store-catalog-db`: catalog DATABASE_URL only.
- `eks-store-orders-db`: orders DATABASE_URL only.

Applications read DATABASE_URL directly. There are no mounted secret-directory overrides. Old CSI-managed Secrets and classes can remain temporarily unused; the new release does not fight their ownership. Server-side apply manages the new Secret data under a dedicated manager. Do not output Secret YAML into CI logs. Password changes take effect in app pods only after rollout.

The bootstrap connects as the RDS master, creates or alters catalog_user/order_user with exactly these passwords, creates missing databases, grants schema access and verifies both user connections. It does not delete customer rows or recreate databases. Existing tables owned by a different historical user may need an explicit reviewed ownership migration: schema grants do not automatically transfer existing table ownership.

## 5. Release through GitHub Actions
Push main or manually run `Release EKS Store (kubectl)` with environment=lab. To avoid an automatic release while reviewing infrastructure, stage changes on a branch and merge only when ready.

Order:
1. Install full requirements; run unit/regression tests.
2. Run bootstrap twice against disposable PostgreSQL 16 (create and update branches), migrate both databases, seed twice and verify records. This CI test is guarded so it cannot run against production by accident.
3. Build/push four container images tagged with the full commit SHA.
4. Install kubectl matching the EKS minor version; connect only to the explicit cluster.
5. Render namespace, ServiceAccounts and ConfigMap; validate/apply the three direct Secrets.
6. Bootstrap -> catalog migration -> orders migration -> catalog seed, waiting and failing at the first unsuccessful Job.
7. Apply frontend/APIs; restart for current configuration; require successful rollout.
8. Apply ingress, upload product images and retry live acceptance tests while ALB targets settle.

All operations workflows use the same concurrency group. Jobs have a 600-second deadline, immediate failure polling and one-day retention for diagnostics. No timeout is silently treated as success. Failure logs are uploaded as an Actions artifact. The release does not change IAM policies, security groups, subnets or CSI resources.

If a container build cannot download the RDS CA bundle, the build fails before deployment. The CA is included in all Python runtime images and `PGSSLROOTCERT` points at it. Do not disable verify-full as a workaround for credential errors.

## 6. Manual deployment
Run in WSL/Linux from repo root, using configured AWS CLI credentials with the required EKS access:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export AWS_REGION=eu-north-1
export ENVIRONMENT=lab
export IMAGE_TAG=FULL_COMMIT_SHA_ALREADY_PUSHED_TO_ALL_FOUR_ECR_REPOSITORIES
bash scripts/deploy.sh
```
`deploy.sh` discovers the catalog IAM role ARN and actual account-suffixed assets bucket name. Override ASSETS_BUCKET/CATALOG_ROLE_ARN only for intentionally different existing names. Rendered YAML is in `.rendered/` and contains identifiers, not database secrets. Do not apply source `${VARIABLE}` YAML directly.

To upload pictures manually:
```bash
python scripts/upload_s3.py --bucket ACTUAL_ASSETS_BUCKET --region eu-north-1 --confirm
```
The normal release does this for you. Product objects use `catalog/` keys matching config/image_mappings.yaml.

## 7. Diagnose without destroying resources
```bash
kubectl get pods,jobs,deploy,svc,ingress -n eks-store
kubectl get events -n eks-store --sort-by=.metadata.creationTimestamp
bash scripts/diagnose.sh
```
Inspect the uniquely named bootstrap Job from the failed run, not an old fixed name:
```bash
kubectl describe job ACTUAL_JOB_NAME -n eks-store
kubectl logs job/ACTUAL_JOB_NAME -n eks-store --all-containers=true
```

| Failure | Meaning/action |
|---|---|
| Required field/URL mismatch | Source secret data is inconsistent; validate master/app fields and encoded URL without sharing values |
| Bootstrap master auth fails | Master secret does not match actual RDS master credentials; verify/update that relationship first |
| Role password syntax error | Corrected source may not be in the image; verify full SHA/image tag and rerun release |
| Bootstrap privilege/ownership error | Use RDS master with intended grants; review existing object ownership |
| RDS TLS/CA failure | Check hostname, bundled CA path, instance CA and correct image; retain verify-full |
| Network timeout | Check node-to-RDS TCP 5432 rule and DNS/private-subnet routes in Terraform |
| ErrImagePull | Exact ECR URI/SHA, node ECR permissions and NAT/endpoints |
| Catalog S3 403 | Catalog IRSA trust and assets bucket/object permissions; GitHub's credentials do not become pod credentials |
| APIs remain 0/1 | Inspect readiness logs and Job success before touching ingress |
| ALB controller absent | Apply existing addons stack; release deliberately does not install infrastructure |
| 502 | Inspect API readiness and Service endpoints; frontend/ALB health alone is not app success |

CI cannot verify your real RDS master password, live IAM trust, security group state or existing data ownership offline. A successful disposable integration gate does not prove these AWS settings are correct.

## 8. Rollback and teardown
Use a known-good SHA or `kubectl rollout undo` for the affected deployment. Database schema/password changes are not undone by Kubernetes rollback; migrations must remain compatible with currently running pods. Back up important RDS data before migrations. Bootstrap aligns database user passwords to Secrets Manager, which can briefly interrupt old app pods until the rollout.

The old pause/resume/recreate workflow is replaced with explicit application removal. It deletes ingress and app Deployments only; RDS, EKS, S3, NAT and ECR remain and may still incur charges. Confirm the ALB is deleted while its controller runs before destroying addons/platform. Use Terraform destroy only intentionally, in dependency order, and inspect every failure. Non-empty ECR/S3 buckets and RDS deletion protection can stop teardown. Bootstrap/state remains protected.

## 9. Production profile
Both environments now resolve consistently, but the provided one-replica HTTP ingress is still a lab baseline. Before using production, configure ACM TLS/DNS, appropriate replicas/resources, database backup/recovery, restricted cluster access and environment approval protections. Do not interpret the filename or workflow name as production certification.
