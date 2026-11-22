# Corrections made to the uploaded repository

- Corrected Psycopg 3 CREATE/ALTER ROLE password DDL using Identifier/Literal composition.
- Bootstrap now requires explicit credentials, preserves password bytes and verifies both users after grants.
- Removed competing application database CSI mounts and secret-file precedence.
- Added distinct direct Kubernetes Secrets; validate all required JSON fields, endpoint consistency and URL/password agreement before applying.
- Added CA bundle to runtime images and restored verify-full TLS.
- Removed application Helm chart/branch; retained existing Terraform addon Helm state/resources intentionally.
- Added strict manifest rendering, dynamic ECR URLs/IRSA/bucket/environment settings and full SHA image tags.
- Added full dependency installation, fail-closed CI and PostgreSQL integration gate before image publishing.
- Added per-run Job names, failure polling, long diagnostic retention and diagnostic artifacts.
- Replaced implicit IAM/security-group/CSI repair mutations with infrastructure prerequisites.
- Removed implicit destructive orphan cleanup and automatic import scripts; kept remote state keys/resource addresses.
- Added environment-specific cluster_name inputs, workflow concurrency and failure-propagating destroys.
- Added product-image upload to release and strict API health acceptance checks.
- Replaced broken lifecycle paths with explicit app removal.
- Archived superseded/unverified documentation; supplied a current deployment/recovery guide.

No AWS infrastructure was accessed or changed to prepare this package. Existing remote state and real DB credentials must still be checked in the target account.
