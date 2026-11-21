"""
Dynamic Terraform Import Generator
Inspects AWS via boto3 for pre-existing resources in the target stack.
Generates a temporary 'generated_imports.tf' containing import blocks ONLY for
resources that actually exist in the AWS account.
Prevents both 'AlreadyExists' and 'Cannot import non-existent remote object' errors.
"""

import os
import sys
import argparse
import boto3
import botocore.exceptions

def check_dynamodb_table(client, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return False
        return False

def check_s3_bucket(client, bucket_name: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket_name)
        return True
    except botocore.exceptions.ClientError:
        return False

def check_iam_role(client, role_name: str) -> bool:
    try:
        client.get_role(RoleName=role_name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchEntity":
            return False
        return False

def check_iam_policy(client, policy_arn: str) -> bool:
    try:
        client.get_policy(PolicyArn=policy_arn)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchEntity":
            return False
        return False

def check_ecr_repo(client, repo_name: str) -> bool:
    try:
        client.describe_repositories(repositoryNames=[repo_name])
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "RepositoryNotFoundException":
            return False
        return False

def check_ecr_lifecycle(client, repo_name: str) -> bool:
    try:
        client.get_lifecycle_policy(repositoryName=repo_name)
        return True
    except botocore.exceptions.ClientError:
        return False

def check_secret(client, secret_id: str) -> bool:
    try:
        resp = client.describe_secret(SecretId=secret_id)
        # Check if secret is scheduled for deletion
        if resp.get("DeletedDate"):
            return False
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") in ["ResourceNotFoundException", "InvalidRequestException"]:
            return False
        return False


def generate_bootstrap_imports(region, project, env, account_id):
    imports = []
    dynamodb = boto3.client("dynamodb", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    iam = boto3.client("iam", region_name=region)

    lock_table = f"{project}-tf-locks-{env}"
    if check_dynamodb_table(dynamodb, lock_table):
        imports.append(f'import {{\n  to = aws_dynamodb_table.tf_locks\n  id = "{lock_table}"\n}}')

    state_bucket = f"{project}-tf-state-{env}-{account_id}"
    if check_s3_bucket(s3, state_bucket):
        imports.append(f'import {{\n  to = aws_s3_bucket.tf_state\n  id = "{state_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_versioning.tf_state\n  id = "{state_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_server_side_encryption_configuration.tf_state\n  id = "{state_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_public_access_block.tf_state\n  id = "{state_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_policy.tf_state_tls_only\n  id = "{state_bucket}"\n}}')

    role_name = f"{project}-github-actions-role-{env}"
    policy_arn = f"arn:aws:iam::{account_id}:policy/{project}-github-ci-policy-{env}"
    if check_iam_role(iam, role_name):
        imports.append(f'import {{\n  to = aws_iam_role.github_actions\n  id = "{role_name}"\n}}')
    if check_iam_policy(iam, policy_arn):
        imports.append(f'import {{\n  to = aws_iam_policy.github_actions_ci\n  id = "{policy_arn}"\n}}')
    if check_iam_role(iam, role_name) and check_iam_policy(iam, policy_arn):
        imports.append(f'import {{\n  to = aws_iam_role_policy_attachment.github_actions\n  id = "{role_name}/{policy_arn}"\n}}')

    return imports


def generate_data_imports(region, project, env, account_id):
    imports = []
    ecr = boto3.client("ecr", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    sm = boto3.client("secretsmanager", region_name=region)

    for svc in ["frontend", "catalog", "orders", "seed"]:
        repo_name = f"{project}-{svc}"
        if check_ecr_repo(ecr, repo_name):
            imports.append(f'import {{\n  to = aws_ecr_repository.services["{svc}"]\n  id = "{repo_name}"\n}}')
            if check_ecr_lifecycle(ecr, repo_name):
                imports.append(f'import {{\n  to = aws_ecr_lifecycle_policy.services["{svc}"]\n  id = "{repo_name}"\n}}')

    assets_bucket = f"{project}-assets-{env}-{account_id}"
    if check_s3_bucket(s3, assets_bucket):
        imports.append(f'import {{\n  to = aws_s3_bucket.assets\n  id = "{assets_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_versioning.assets\n  id = "{assets_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_public_access_block.assets\n  id = "{assets_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_server_side_encryption_configuration.assets\n  id = "{assets_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_policy.assets_tls_only\n  id = "{assets_bucket}"\n}}')

    artifacts_bucket = f"{project}-artifacts-{env}-{account_id}"
    if check_s3_bucket(s3, artifacts_bucket):
        imports.append(f'import {{\n  to = aws_s3_bucket.artifacts\n  id = "{artifacts_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_versioning.artifacts\n  id = "{artifacts_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_public_access_block.artifacts\n  id = "{artifacts_bucket}"\n}}')
        imports.append(f'import {{\n  to = aws_s3_bucket_server_side_encryption_configuration.artifacts\n  id = "{artifacts_bucket}"\n}}')

    for secret_key, resource_name in [
        (f"{project}/{env}/rds/master", "aws_secretsmanager_secret.rds_master"),
        (f"{project}/{env}/catalog-db", "aws_secretsmanager_secret.catalog_db"),
        (f"{project}/{env}/order-db", "aws_secretsmanager_secret.order_db"),
    ]:
        if check_secret(sm, secret_key):
            imports.append(f'import {{\n  to = {resource_name}\n  id = "{secret_key}"\n}}')

    return imports


def generate_platform_imports(region, project, env, account_id):
    imports = []
    iam = boto3.client("iam", region_name=region)

    cluster_role = f"{project}-eks-cluster-role-{env}"
    node_role = f"{project}-eks-node-role-{env}"
    if check_iam_role(iam, cluster_role):
        imports.append(f'import {{\n  to = aws_iam_role.cluster\n  id = "{cluster_role}"\n}}')
    if check_iam_role(iam, node_role):
        imports.append(f'import {{\n  to = aws_iam_role.node\n  id = "{node_role}"\n}}')

    for pol_name, resource_name in [
        (f"{project}-catalog-policy-{env}", "aws_iam_policy.catalog_service"),
        (f"{project}-order-policy-{env}", "aws_iam_policy.order_service"),
        (f"{project}-db-job-policy-{env}", "aws_iam_policy.db_job"),
    ]:
        pol_arn = f"arn:aws:iam::{account_id}:policy/{pol_name}"
        if check_iam_policy(iam, pol_arn):
            imports.append(f'import {{\n  to = {resource_name}\n  id = "{pol_arn}"\n}}')

    return imports


def main():
    parser = argparse.ArgumentParser(description="Generate dynamic Terraform imports")
    parser.add_argument("--stack", required=True, help="Stack name (bootstrap, data, platform, network, addons)")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-north-1"))
    parser.add_argument("--project", default=os.environ.get("PROJECT_NAME", "eks-store"))
    parser.add_argument("--env", default=os.environ.get("ENVIRONMENT", "lab"))
    parser.add_argument("--account", default=os.environ.get("ACCOUNT_ID", ""))
    args = parser.parse_args()

    if not args.account:
        try:
            sts = boto3.client("sts", region_name=args.region)
            args.account = sts.get_caller_identity()["Account"]
        except Exception as e:
            print(f"Warning: Could not resolve AWS Account ID: {e}")
            return

    stack_dir = os.path.join("infra", args.stack)
    out_file = os.path.join(stack_dir, "generated_imports.tf")

    # Clean up previous generated imports file if present
    if os.path.exists(out_file):
        os.remove(out_file)

    imports = []
    print(f"Checking existing AWS resources for stack '{args.stack}' in {args.region} ({args.project}-{args.env})...")

    try:
        if args.stack == "bootstrap":
            imports = generate_bootstrap_imports(args.region, args.project, args.env, args.account)
        elif args.stack == "data":
            imports = generate_data_imports(args.region, args.project, args.env, args.account)
        elif args.stack == "platform":
            imports = generate_platform_imports(args.region, args.project, args.env, args.account)
    except Exception as e:
        print(f"Note: Error during AWS preflight check for {args.stack}: {e}")

    if imports:
        print(f"Found {len(imports)} pre-existing AWS resources for {args.stack}. Writing {out_file}...")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("# Automatically generated by .github/scripts/generate-imports.py\n")
            f.write("# Contains import blocks strictly for verified pre-existing AWS resources.\n\n")
            f.write("\n\n".join(imports) + "\n")
    else:
        print(f"No pre-existing resources detected for {args.stack} that require adoption. Ready for creation.")


if __name__ == "__main__":
    main()
