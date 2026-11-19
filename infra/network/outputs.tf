output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs for EKS worker nodes"
  value       = aws_subnet.private_app[*].id
}

output "isolated_db_subnet_ids" {
  description = "Isolated database subnet IDs for RDS"
  value       = aws_subnet.isolated_db[*].id
}

output "rds_subnet_group_name" {
  description = "RDS DB subnet group name"
  value       = aws_db_subnet_group.rds.name
}

output "alb_security_group_id" {
  description = "Security group ID for public Application Load Balancer"
  value       = aws_security_group.alb.id
}

output "eks_nodes_security_group_id" {
  description = "Security group ID for EKS worker nodes"
  value       = aws_security_group.eks_nodes.id
}

output "rds_security_group_id" {
  description = "Security group ID for RDS PostgreSQL"
  value       = aws_security_group.rds.id
}
