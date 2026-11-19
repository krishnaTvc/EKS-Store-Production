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
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  type        = string
}

variable "cluster_certificate_authority_data" {
  description = "Cluster CA certificate data"
  type        = string
}

variable "oidc_provider_arn" {
  description = "OIDC Provider ARN from platform stack"
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC Provider URL from platform stack"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID from network stack"
  type        = string
}
