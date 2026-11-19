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

variable "db_instance_class" {
  description = "RDS instance class (small, cost-effective for demo/lab)"
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "deletion_protection" {
  description = "Protect RDS instance from accidental deletion"
  type        = bool
  default     = false
}

variable "rds_subnet_group_name" {
  description = "Name of the RDS DB subnet group from the network stack"
  type        = string
}

variable "rds_security_group_id" {
  description = "Security group ID for RDS from the network stack"
  type        = string
}
