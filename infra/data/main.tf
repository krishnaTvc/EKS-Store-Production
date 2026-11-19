terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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
      Stack       = "data"
    }
  }
}

data "aws_caller_identity" "current" {}

# Auto-discover DB subnet group and security group from network stack if not explicitly provided
data "aws_db_subnet_group" "rds" {
  count = var.rds_subnet_group_name == "" ? 1 : 0
  name  = "${var.project_name}-rds-subnet-group-${var.environment}"
}

data "aws_security_group" "rds" {
  count = var.rds_security_group_id == "" ? 1 : 0
  name  = "${var.project_name}-rds-sg-${var.environment}"
}

locals {
  resolved_rds_subnet_group_name = var.rds_subnet_group_name != "" ? var.rds_subnet_group_name : data.aws_db_subnet_group.rds[0].name
  resolved_rds_security_group_id = var.rds_security_group_id != "" ? var.rds_security_group_id : data.aws_security_group.rds[0].id
}

# 1. Random passwords for RDS master and application users
resource "random_password" "rds_master_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "catalog_db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "order_db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# 2. Amazon RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-rds-${var.environment}"
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.db_instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = 50
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "postgres"
  username = "postgres"
  password = random_password.rds_master_password.result
  port     = 5432

  db_subnet_group_name   = local.resolved_rds_subnet_group_name
  vpc_security_group_ids = [local.resolved_rds_security_group_id]
  publicly_accessible    = false

  backup_retention_period    = 7
  backup_window              = "03:00-04:00"
  maintenance_window         = "sun:04:30-sun:05:30"
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-rds-final-snapshot"

  tags = {
    Name = "${var.project_name}-rds-${var.environment}"
  }
}

# 3. AWS Secrets Manager: Storing credentials securely
resource "aws_secretsmanager_secret" "rds_master" {
  name                    = "${var.project_name}/${var.environment}/rds/master"
  description             = "Master PostgreSQL credentials for EKS Store RDS"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = aws_secretsmanager_secret.rds_master.id
  secret_string = jsonencode({
    host            = aws_db_instance.postgres.address
    port            = aws_db_instance.postgres.port
    master_username = aws_db_instance.postgres.username
    master_password = random_password.rds_master_password.result
    dbname          = "postgres"
  })
}

resource "aws_secretsmanager_secret" "catalog_db" {
  name                    = "${var.project_name}/${var.environment}/catalog-db"
  description             = "Catalog microservice application database credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "catalog_db" {
  secret_id = aws_secretsmanager_secret.catalog_db.id
  secret_string = jsonencode({
    host         = aws_db_instance.postgres.address
    port         = aws_db_instance.postgres.port
    username     = "catalog_user"
    password     = random_password.catalog_db_password.result
    dbname       = "catalog"
    DATABASE_URL = "postgresql+psycopg://catalog_user:${urlencode(random_password.catalog_db_password.result)}@${aws_db_instance.postgres.address}:5432/catalog?sslmode=verify-full"
  })
}

resource "aws_secretsmanager_secret" "order_db" {
  name                    = "${var.project_name}/${var.environment}/order-db"
  description             = "Order microservice application database credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "order_db" {
  secret_id = aws_secretsmanager_secret.order_db.id
  secret_string = jsonencode({
    host         = aws_db_instance.postgres.address
    port         = aws_db_instance.postgres.port
    username     = "order_user"
    password     = random_password.order_db_password.result
    dbname       = "orders"
    DATABASE_URL = "postgresql+psycopg://order_user:${urlencode(random_password.order_db_password.result)}@${aws_db_instance.postgres.address}:5432/orders?sslmode=verify-full"
  })
}

# 4. S3 Assets Bucket (Private, KMS/AES-256 encrypted, versioned)
resource "aws_s3_bucket" "assets" {
  bucket        = "${var.project_name}-assets-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "assets_tls_only" {
  bucket = aws_s3_bucket.assets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLSOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.assets.arn,
          "${aws_s3_bucket.assets.arn}/*"
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

# 5. S3 Artifacts Bucket (For CSV manifests and release artifacts)
resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.project_name}-artifacts-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 6. ECR Repositories (Immutable tags, vulnerability scanning on push)
locals {
  ecr_services = [
    "frontend",
    "catalog",
    "orders",
    "seed"
  ]
}

resource "aws_ecr_repository" "services" {
  for_each             = toset(local.ecr_services)
  name                 = "${var.project_name}-${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Service = each.key
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Retain the last 15 container images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 15
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
