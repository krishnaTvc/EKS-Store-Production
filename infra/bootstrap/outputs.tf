output "state_bucket_name" {
  description = "The name of the S3 bucket created for Terraform state storage"
  value       = aws_s3_bucket.tf_state.id
}

output "dynamodb_table_name" {
  description = "The name of the DynamoDB table for Terraform state locking"
  value       = aws_dynamodb_table.tf_locks.id
}

output "github_actions_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions via OIDC"
  value       = aws_iam_role.github_actions.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
