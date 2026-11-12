variable "name" {
  description = "Name prefix for IAM resources."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name (the deploy role may describe only this cluster)."
  type        = string
}

variable "ecr_repository_arns" {
  description = "ECR repositories the deploy role may push to."
  type        = list(string)
}

variable "db_secret_arn" {
  description = "Secrets Manager secret the deploy role may read (RDS master password)."
  type        = string
}

variable "github_repository" {
  description = "owner/repo trusted to assume the deploy role. Empty disables CI/CD IAM."
  type        = string
  default     = ""
}

variable "github_environment" {
  description = "GitHub Environment the deploy job must run in."
  type        = string
  default     = "production"
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider (false = reuse an existing one)."
  type        = bool
  default     = true
}
