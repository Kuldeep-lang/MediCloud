output "repository_urls" {
  description = "Map of repository name to push URL."
  value       = { for name, repo in aws_ecr_repository.this : name => repo.repository_url }
}

output "repository_arns" {
  description = "Repository ARNs (for IAM policies)."
  value       = [for repo in aws_ecr_repository.this : repo.arn]
}
