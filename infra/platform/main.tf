terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "platform"
    }
  }
}

data "aws_caller_identity" "current" {}

# Auto-discover VPC, Subnets, SGs, and Secrets from previous stacks if not explicitly passed
data "aws_vpc" "main" {
  count = var.vpc_id == "" ? 1 : 0
  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

locals {
  resolved_vpc_id = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.main[0].id
}

data "aws_subnets" "private" {
  count = length(var.private_subnet_ids) == 0 ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [local.resolved_vpc_id]
  }
  tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

data "aws_security_group" "eks_nodes" {
  count = var.eks_nodes_security_group_id == "" ? 1 : 0
  name  = "${var.project_name}-eks-nodes-sg-${var.environment}"
}

data "aws_s3_bucket" "assets" {
  count  = var.assets_bucket_arn == "" ? 1 : 0
  bucket = "${var.project_name}-assets-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

data "aws_secretsmanager_secret" "catalog_db" {
  count = var.catalog_db_secret_arn == "" ? 1 : 0
  name  = "${var.project_name}/${var.environment}/catalog-db"
}

data "aws_secretsmanager_secret" "order_db" {
  count = var.order_db_secret_arn == "" ? 1 : 0
  name  = "${var.project_name}/${var.environment}/order-db"
}

data "aws_secretsmanager_secret" "rds_master" {
  count = var.rds_master_secret_arn == "" ? 1 : 0
  name  = "${var.project_name}/${var.environment}/rds/master"
}

locals {
  resolved_private_subnet_ids          = length(var.private_subnet_ids) > 0 ? var.private_subnet_ids : data.aws_subnets.private[0].ids
  resolved_eks_nodes_security_group_id = var.eks_nodes_security_group_id != "" ? var.eks_nodes_security_group_id : data.aws_security_group.eks_nodes[0].id
  resolved_assets_bucket_arn           = var.assets_bucket_arn != "" ? var.assets_bucket_arn : data.aws_s3_bucket.assets[0].arn
  resolved_catalog_db_secret_arn       = var.catalog_db_secret_arn != "" ? var.catalog_db_secret_arn : data.aws_secretsmanager_secret.catalog_db[0].arn
  resolved_order_db_secret_arn         = var.order_db_secret_arn != "" ? var.order_db_secret_arn : data.aws_secretsmanager_secret.order_db[0].arn
  resolved_rds_master_secret_arn       = var.rds_master_secret_arn != "" ? var.rds_master_secret_arn : data.aws_secretsmanager_secret.rds_master[0].arn
}

# 1. EKS Cluster IAM Role
resource "aws_iam_role" "cluster" {
  name = "${var.project_name}-eks-cluster-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSClusterPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSVPCResourceController" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.name
}

# 2. EKS Control Plane
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version != "" ? var.kubernetes_version : null

  vpc_config {
    subnet_ids              = local.resolved_private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    security_group_ids      = [local.resolved_eks_nodes_security_group_id]
  }

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator"]

  depends_on = [
    aws_iam_role_policy_attachment.cluster_AmazonEKSClusterPolicy,
    aws_iam_role_policy_attachment.cluster_AmazonEKSVPCResourceController,
  ]

  tags = {
    Name = var.cluster_name
  }
}

# 3. OIDC Provider for IAM Roles for Service Accounts (IRSA)
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# 4. EKS Managed Node Group IAM Role
resource "aws_iam_role" "node" {
  name = "${var.project_name}-eks-node-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

# 5. Node Launch Template (Enforces IMDSv2 and Volume Encryption)
resource "aws_launch_template" "node" {
  name_prefix   = "${var.project_name}-node-lt-"
  instance_type = var.node_instance_types[0]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name                                        = "${var.cluster_name}-node"
      "kubernetes.io/cluster/${var.cluster_name}" = "owned"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 6. Managed Node Group (Placed in Private Application Subnets)
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-nodes-${var.environment}"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = local.resolved_private_subnet_ids

  scaling_config {
    desired_size = var.node_desired_size
    max_size     = var.node_max_size
    min_size     = var.node_min_size
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = "$Latest"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.node_AmazonEKS_CNI_Policy,
    aws_iam_role_policy_attachment.node_AmazonEC2ContainerRegistryReadOnly,
  ]

  tags = {
    Name = "${var.project_name}-nodes-${var.environment}"
  }
}

# 7. Workload Identity (IRSA) for Application Pods
# Catalog Service Role: Scoped S3 assets read + Secrets Manager read
resource "aws_iam_role" "catalog_service" {
  name = "${var.project_name}-catalog-sa-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:eks-store:catalog-service-sa"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "catalog_service" {
  name        = "${var.project_name}-catalog-policy-${var.environment}"
  description = "Scoped permissions for catalog service pod: S3 assets and Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3AssetsGetObjectOnly"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${local.resolved_assets_bucket_arn}/*"
      },
      {
        Sid    = "ReadCatalogDatabaseSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = local.resolved_catalog_db_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "catalog_service" {
  role       = aws_iam_role.catalog_service.name
  policy_arn = aws_iam_policy.catalog_service.arn
}

# Order Service Role: Secrets Manager read for order-db
resource "aws_iam_role" "order_service" {
  name = "${var.project_name}-order-sa-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:eks-store:order-service-sa"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "order_service" {
  name        = "${var.project_name}-order-policy-${var.environment}"
  description = "Permissions for order service pod to read order-db credentials"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadOrderDatabaseSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = local.resolved_order_db_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "order_service" {
  role       = aws_iam_role.order_service.name
  policy_arn = aws_iam_policy.order_service.arn
}

# Database Migration & Seed Job Role
resource "aws_iam_role" "db_job" {
  name = "${var.project_name}-db-job-sa-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:eks-store:db-job-sa"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "db_job" {
  name        = "${var.project_name}-db-job-policy-${var.environment}"
  description = "Permissions for pre-deploy migration and bootstrap jobs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSecretsForMigrations"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          local.resolved_rds_master_secret_arn,
          local.resolved_catalog_db_secret_arn,
          local.resolved_order_db_secret_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "db_job" {
  role       = aws_iam_role.db_job.name
  policy_arn = aws_iam_policy.db_job.arn
}

# 8. EKS Access Entries (for GitHub Actions CI and Admin Users)
resource "aws_eks_access_entry" "github_actions" {
  count         = var.github_actions_role_arn != "" ? 1 : 0
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.github_actions_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions_admin" {
  count         = var.github_actions_role_arn != "" ? 1 : 0
  cluster_name  = aws_eks_cluster.main.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = var.github_actions_role_arn

  access_scope {
    type = "cluster"
  }
}
