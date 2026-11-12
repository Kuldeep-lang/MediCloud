# Defaults are deliberately cost-conscious for an academic demonstration.
# Copy terraform.tfvars.example to terraform.tfvars (git-ignored) to override.

# ---------------------------------------------------------------- general
variable "project_name" {
  description = "Prefix for resource names and the Project tag."
  type        = string
  default     = "medicloud"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "Use 3-21 lowercase letters, digits or dashes, starting with a letter."
  }
}

variable "environment" {
  description = "Environment name, used in tags."
  type        = string
  default     = "demo"
}

variable "aws_region" {
  description = "AWS region for every resource."
  type        = string
  default     = "ap-southeast-2"
}

# ---------------------------------------------------------------- network
variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 16
    error_message = "vpc_cidr must be a valid CIDR of /16 or larger (subnets are carved from it)."
  }
}

variable "enable_vpc_flow_logs" {
  description = "Log rejected network traffic to CloudWatch (3-day retention, negligible cost)."
  type        = bool
  default     = true
}

variable "az_count" {
  description = "Availability zones to use. EKS and RDS subnet groups both require at least 2."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

# ---------------------------------------------------------------- EKS
variable "kubernetes_version" {
  description = "EKS Kubernetes version. Must be in STANDARD support (extended support costs 6x)."
  type        = string
  default     = "1.37"
}

variable "cluster_endpoint_public_access_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach the public Kubernetes API endpoint (IAM authentication is always
    required as well). Restricting it to your IP is more secure, but GitHub-hosted runners
    use changing IPs, so the CD pipeline can then only deploy from an allowed address.
    The default stays open by decision D37 so the Phase 7 pipeline can deploy.
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = alltrue([for c in var.cluster_endpoint_public_access_cidrs : can(cidrhost(c, 0))])
    error_message = "Every entry must be a valid CIDR, e.g. 203.0.113.10/32."
  }
}

variable "cluster_log_types" {
  description = "Control-plane log types sent to CloudWatch (each adds ingestion cost)."
  type        = list(string)
  default     = ["audit", "authenticator"]
}

variable "node_instance_types" {
  description = <<-EOT
    Instance types for the managed node group (x86_64, because the images are amd64).
    c7i-flex.large (2 vCPU, 4 GiB, 29 pods) is the smallest Free-plan-eligible type with the
    memory of a t3.medium; AWS Free-plan accounts can only launch eligible types (D38).
    On a Paid-plan account, ["t3.medium"] is about $0.058/h cheaper per node.
  EOT
  type        = list(string)
  default     = ["c7i-flex.large"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND, or SPOT (cheaper, but nodes can be reclaimed; may be unavailable on Free-plan accounts)."
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_desired_size" {
  description = "Initial number of worker nodes."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3
}

# ---------------------------------------------------------------- RDS
variable "db_instance_class" {
  description = "RDS instance class (db.t4g.micro is the smallest Graviton class)."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_engine_version" {
  description = "PostgreSQL major version - matches the local Docker/Kubernetes image (17)."
  type        = string
  default     = "17"
}

variable "db_allocated_storage" {
  description = "Storage in GiB (gp3)."
  type        = number
  default     = 20
}

variable "db_multi_az" {
  description = "Multi-AZ standby (doubles the RDS cost). Off for the demo."
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = <<-EOT
    Automated backup retention in days (1-35). AWS Free-plan accounts reject more than 1
    (FreeTierRestrictionError, seen on the first apply - D38). On a Paid-plan account use 7:
    backup storage up to the DB size is included at no cost.
  EOT
  type        = number
  default     = 1
}

variable "db_deletion_protection" {
  description = "Block deletion of the database. Off so the demo can be destroyed cleanly."
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "Skip the final snapshot on destroy (snapshots keep costing money)."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- ECR
variable "ecr_repositories" {
  description = "Container repositories to create."
  type        = list(string)
  default     = ["medicloud-backend", "medicloud-frontend"]
}

variable "ecr_force_delete" {
  description = "Allow destroy to delete repositories that still contain images."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- CI/CD (GitHub OIDC)
variable "github_repository" {
  description = "GitHub repository allowed to deploy, as owner/name. Empty = no CI/CD role."
  type        = string
  default     = ""

  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use the form owner/repository."
  }
}

variable "github_environment" {
  description = "GitHub Environment the deploy job runs in (the role trusts only this environment)."
  type        = string
  default     = "production"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- Ansible-managed VM (Phase 6)
variable "enable_app_host" {
  description = "Create the Ubuntu VM that Ansible configures (adds ~$0.035/h with t3.small)."
  type        = bool
  default     = false
}

variable "app_host_instance_type" {
  description = "Instance type of the Ansible-managed VM (must be Free-plan eligible on Free-plan accounts)."
  type        = string
  default     = "t3.small"
}

variable "app_host_ssh_public_key" {
  description = "OpenSSH public key for Ansible (required when enable_app_host = true)."
  type        = string
  default     = ""
}

variable "app_host_ssh_cidrs" {
  description = "CIDRs allowed to SSH to the VM, normally your own IP as /32 (required when enable_app_host = true)."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------- cost guardrail
variable "budget_alert_email" {
  description = "E-mail for AWS Budget alerts. Empty = no budget is created."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly budget; alerts at 25%, 50% and 100% of actual spend and 100% forecast."
  type        = number
  default     = 20
}
