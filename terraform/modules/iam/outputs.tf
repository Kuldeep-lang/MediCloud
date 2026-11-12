output "cluster_role_arn" {
  description = "IAM role assumed by the EKS control plane."
  value       = aws_iam_role.cluster.arn
}

output "node_role_arn" {
  description = "IAM role for worker nodes."
  value       = aws_iam_role.node.arn
}

output "cluster_role_policy_attachments" {
  description = "Attachment IDs - lets the eks module wait until the policies are in place."
  value       = [for a in aws_iam_role_policy_attachment.cluster : a.id]
}

output "node_role_policy_attachments" {
  description = "Attachment IDs - lets the node group wait until the policies are in place."
  value       = [for a in aws_iam_role_policy_attachment.node : a.id]
}

output "github_deploy_role_arn" {
  description = "Role for GitHub Actions to assume via OIDC (null when disabled)."
  value       = try(aws_iam_role.github_deploy[0].arn, null)
}
