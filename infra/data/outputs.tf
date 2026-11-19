output "rds_endpoint" {
  description = "The connection endpoint of the RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "The hostname address of the RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "The port of the RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.port
}

output "rds_master_secret_arn" {
  description = "ARN of Secrets Manager secret containing RDS master credentials"
  value       = aws_secretsmanager_secret.rds_master.arn
}

output "catalog_db_secret_arn" {
  description = "ARN of Secrets Manager secret containing catalog application database credentials"
  value       = aws_secretsmanager_secret.catalog_db.arn
}

output "order_db_secret_arn" {
  description = "ARN of Secrets Manager secret containing order application database credentials"
  value       = aws_secretsmanager_secret.order_db.arn
}

output "assets_bucket_name" {
  description = "S3 bucket for catalog product images"
  value       = aws_s3_bucket.assets.id
}

output "assets_bucket_arn" {
  description = "ARN of S3 bucket for catalog product images"
  value       = aws_s3_bucket.assets.arn
}

output "artifacts_bucket_name" {
  description = "S3 bucket for catalog CSV datasets and checksum manifests"
  value       = aws_s3_bucket.artifacts.id
}

output "ecr_repository_urls" {
  description = "Map of ECR repository URLs for frontend, catalog, orders, and seed images"
  value = {
    for k, v in aws_ecr_repository.services : k => v.repository_url
  }
}
