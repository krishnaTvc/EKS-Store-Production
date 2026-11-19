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
  description = "EKS Cluster name for subnet discovery tags"
  type        = string
  default     = "eks-store-lab"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to deploy across"
  type        = list(string)
  default     = ["eu-north-1a", "eu-north-1b"]
}

variable "enable_nat_gateway" {
  description = "Toggle NAT Gateway for cost control during extended cluster pauses"
  type        = bool
  default     = true
}
