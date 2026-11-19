output "cluster_name" {
  description = "The name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "The Kubernetes API server endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster control plane"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC provider for IRSA"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "URL of the OIDC provider for IRSA"
  value       = aws_iam_openid_connect_provider.cluster.url
}

output "catalog_service_role_arn" {
  description = "IAM role ARN for catalog-service service account"
  value       = aws_iam_role.catalog_service.arn
}

output "order_service_role_arn" {
  description = "IAM role ARN for order-service service account"
  value       = aws_iam_role.order_service.arn
}

output "db_job_role_arn" {
  description = "IAM role ARN for database bootstrap and migration jobs"
  value       = aws_iam_role.db_job.arn
}
