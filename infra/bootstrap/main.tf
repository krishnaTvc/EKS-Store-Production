terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

# Import blocks to adopt pre-existing AWS resources safely without conflict
import {
  to = aws_s3_bucket.tf_state
  id = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

import {
  to = aws_s3_bucket_versioning.tf_state
  id = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.tf_state
  id = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

import {
  to = aws_s3_bucket_public_access_block.tf_state
  id = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

import {
  to = aws_s3_bucket_policy.tf_state_tls_only
  id = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

import {
  to = aws_dynamodb_table.tf_locks
  id = "${var.project_name}-tf-locks-${var.environment}"
}

import {
  to = aws_iam_policy.github_actions_ci
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.project_name}-github-ci-policy-${var.environment}"
}

# 1. Dedicated S3 Bucket for Terraform Remote State
resource "aws_s3_bucket" "tf_state" {
  bucket        = "${var.project_name}-tf-state-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "tf_state_tls_only" {
  bucket = aws_s3_bucket.tf_state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.tf_state.arn,
          "${aws_s3_bucket.tf_state.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# 2. DynamoDB Table for Distributed State Locking
resource "aws_dynamodb_table" "tf_locks" {
  name         = "${var.project_name}-tf-locks-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

# 3. GitHub Actions OIDC Identity Provider (reuses existing provider if already in account)
data "tls_certificate" "github" {
  count = var.create_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  count           = var.create_oidc_provider ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github[0].certificates[0].sha1_fingerprint]
}

locals {
  github_oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

# 4. Scoped IAM Role for GitHub Actions CI/CD Pipeline
resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = local.github_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "github_actions_ci" {
  name        = "${var.project_name}-github-ci-policy-${var.environment}"
  description = "Permissions for GitHub Actions to manage ECR, S3 assets, EKS, and Terraform state"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformStateAccess"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.tf_state.arn,
          "${aws_s3_bucket.tf_state.arn}/*"
        ]
      },
      {
        Sid    = "TerraformLockingAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.tf_locks.arn
      },
      {
        Sid    = "ECRAuthAndPush"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:ListImages"
        ]
        Resource = "*"
      },
      {
        Sid    = "EKSClusterDescribeAndAccess"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_ci.arn
}
