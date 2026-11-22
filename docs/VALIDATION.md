# Verification record

## Completed locally
- 40 Python tests: existing application tests plus deployment regression checks (final result captured in test-results.xml).
- PostgreSQL 16.2 standalone backend executed all four actual generated CREATE/ALTER ROLE password statements successfully, including an apostrophe in the password.
- PostgreSQL 16.2 standalone backend executed both services' Alembic-generated migration SQL successfully in separate databases.
- Strict YAML renderer regression checked three Deployments, four Jobs, removal of database CSI dependencies, new Secret references, retained frontend writable volumes and rejection of missing variables.
- Credential checks cover missing fields, stale URLs, endpoint mismatches and URL-encoded special-character passwords.
- Python source parsing and all shell/workflow embedded shell syntax checks passed.
- Terraform 1.9.8 fmt check and full HCL parsing passed.
- Terraform provider downloads/initialization were attempted. Provider schema validation cannot complete in this execution environment because provider IPC sockets are unavailable; terraform validate is enforced in GitHub PR checks. No successful provider-schema validation or AWS plan is claimed.

## Checks added to GitHub CI, not executed live here
The release now starts a disposable PostgreSQL 16 service and runs scripts/test_postgres_integration.py before building images. It tests actual network authentication, bootstrap twice with password changes, both migrations and seeding twice. The local environment cannot create the sockets needed to run that full network integration gate. The local standalone SQL checks are useful evidence, not a substitute for that gate.

## Not verified in your AWS account
Docker builds, EKS apply, actual RDS master/application credentials, IAM/IRSA trust, security groups, S3 uploads, ALB target health, existing table ownership and order persistence. No AWS resources were accessed or modified.

Tests were prepared using Python 3.12; GitHub Actions/application images use Python 3.11. Existing dependency/deprecation warnings remain. The project is a lab baseline, not a production availability/security certification.
