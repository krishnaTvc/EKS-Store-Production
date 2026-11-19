output "alb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  value       = aws_iam_role.aws_load_balancer_controller.arn
}

output "alb_controller_release_status" {
  description = "Status of AWS Load Balancer Controller helm release"
  value       = helm_release.aws_load_balancer_controller.status
}
