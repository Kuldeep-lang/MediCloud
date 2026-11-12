output "aws_region" {
  description = "Region everything was created in."
  value       = var.aws_region
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes version running on EKS."
  value       = module.eks.cluster_version
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "ecr_repository_urls" {
  description = "Push targets for the container images."
  value       = module.ecr.repository_urls
}

output "rds_endpoint" {
  description = "PostgreSQL host name (private - reachable only from the cluster)."
  value       = module.rds.address
}

output "rds_port" {
  description = "PostgreSQL port."
  value       = module.rds.port
}

output "rds_master_secret_arn" {
  description = "Secrets Manager secret holding the RDS-managed master password (never in state)."
  value       = module.rds.master_user_secret_arn
}

output "github_deploy_role_arn" {
  description = "IAM role for GitHub Actions (store as the AWS_ROLE_ARN secret). Null if disabled."
  value       = module.iam.github_deploy_role_arn
}

output "nat_public_ip" {
  description = "Public IP that cluster egress traffic appears from."
  value       = module.vpc.nat_public_ip
}

output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "app_host_public_ip" {
  description = "Public IP of the Ansible-managed VM (null when enable_app_host = false)."
  value       = try(module.app_host[0].public_ip, null)
}

output "app_host_private_ip" {
  description = "Private IP of the Ansible-managed VM, for Prometheus scraping (null when disabled)."
  value       = try(module.app_host[0].private_ip, null)
}
