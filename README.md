# EKS Store - repaired RDS deployment

**Start with [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Existing AWS resources do not need to be destroyed.**

This edition keeps the architecture in your latest uploaded repo: EKS + private RDS PostgreSQL + S3 images + private ECR images. It repairs the existing project rather than switching to a different database topology.

- Application deployment: plain `kubectl`, one ordered path.
- GitHub AWS authentication: existing `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` repository secrets.
- Database secrets: GitHub reads three validated Secrets Manager objects and creates three dedicated Kubernetes Secrets. No application database CSI mounts or secret-file fallbacks.
- Catalog pod still uses its existing IRSA role for private S3 reads/presigned URLs.
- Bootstrap uses safely composed PostgreSQL role/password DDL and exact generated passwords, with no cloud password defaults.
- CI: complete Python requirements, regression tests and disposable PostgreSQL 16 integration before image build/push.
- Infrastructure: existing Terraform resource addresses/backends remain. No orphan deletion or implicit import scripts run during plan/apply.
- Terraform addon Helm resources are intentionally retained for compatibility with existing addon state; the application Helm chart/branch is removed. See deployment guide before modifying addon ownership.

Run locally with your configured AWS CLI and existing cluster:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ENVIRONMENT=lab IMAGE_TAG=FULL_SHA_ALREADY_IN_ECR bash scripts/deploy.sh
```

Normally use the GitHub Actions release workflow instead; it builds the exact SHA automatically. See `docs/CHANGES.md` and `docs/VALIDATION.md` for changes and verification limits. Historical docs under docs/history are superseded and are not evidence of a successful AWS run.
