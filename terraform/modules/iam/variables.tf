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

variable "github_owner_id" {
  description = "Numeric GitHub owner ID. Set with github_repository_id when the OIDC subject uses immutable IDs (owner@id/repo@id)."
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[0-9]*$", var.github_owner_id))
    error_message = "github_owner_id is a number, e.g. 12345678."
  }
}

variable "github_repository_id" {
  description = "Numeric GitHub repository ID (see github_owner_id)."
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[0-9]*$", var.github_repository_id))
    error_message = "github_repository_id is a number, e.g. 123456789."
  }
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
