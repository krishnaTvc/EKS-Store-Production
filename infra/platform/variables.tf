variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "eks-store"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "lab"
}

variable "cluster_name" {
  description = "EKS Cluster Name"
  type        = string
  default     = "eks-store-lab"
}

variable "kubernetes_version" {
  description = "Kubernetes Version"
  type        = string
  default     = "1.30"
}

variable "node_instance_types" {
  description = "EC2 instance types for managed node group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 3
}

variable "vpc_id" {
  description = "VPC ID from network stack"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private application subnet IDs from network stack"
  type        = list(string)
}

variable "eks_nodes_security_group_id" {
  description = "EKS worker nodes security group ID from network stack"
  type        = string
}

variable "assets_bucket_arn" {
  description = "ARN of S3 assets bucket from data stack"
  type        = string
}

variable "catalog_db_secret_arn" {
  description = "ARN of catalog database secret from data stack"
  type        = string
}

variable "order_db_secret_arn" {
  description = "ARN of order database secret from data stack"
  type        = string
}

variable "rds_master_secret_arn" {
  description = "ARN of RDS master credentials secret from data stack"
  type        = string
}

variable "github_actions_role_arn" {
  description = "ARN of GitHub Actions IAM role for cluster access entry"
  type        = string
  default     = ""
}
