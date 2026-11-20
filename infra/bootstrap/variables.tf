variable "aws_region" {
  description = "AWS region for infrastructure provisioning"
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "eks-store"
}

variable "environment" {
  description = "Deployment environment (e.g., lab, production)"
  type        = string
  default     = "lab"
}

variable "github_repo" {
  description = "GitHub repository owner/name for OIDC trust (e.g., username/EKS-Store-Production)"
  type        = string
  default     = "krishnaTvc/EKS-Store-Production"
}

variable "create_oidc_provider" {
  description = "Whether to create the GitHub OIDC provider. Defaults to false because token.actions.githubusercontent.com already exists in AWS account."
  type        = bool
  default     = false
}
