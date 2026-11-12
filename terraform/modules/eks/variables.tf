variable "name" {
  description = "Cluster name (also the prefix for related resources)."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes minor version (must be in EKS standard support)."
  type        = string
}

variable "cluster_role_arn" {
  description = "IAM role for the EKS control plane."
  type        = string
}

variable "node_role_arn" {
  description = "IAM role for worker nodes."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the control-plane ENIs and the nodes."
  type        = list(string)
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint."
  type        = list(string)
}

variable "cluster_log_types" {
  description = "Control-plane log types to send to CloudWatch."
  type        = list(string)
}

variable "instance_types" {
  description = "Node instance types."
  type        = list(string)
}

variable "capacity_type" {
  description = "ON_DEMAND or SPOT."
  type        = string
}

variable "desired_size" {
  description = "Initial node count."
  type        = number
}

variable "min_size" {
  description = "Minimum node count."
  type        = number
}

variable "max_size" {
  description = "Maximum node count."
  type        = number
}

variable "enable_deploy_access" {
  description = "Grant the CI/CD role namespace-scoped cluster access (requires deploy_role_arn)."
  type        = bool
  default     = false
}

variable "deploy_role_arn" {
  description = "CI/CD role granted namespace-scoped access when enable_deploy_access is true."
  type        = string
  default     = null
}

variable "cluster_role_dependencies" {
  description = "Values that must exist before the cluster is created (IAM attachments)."
  type        = list(string)
  default     = []
}

variable "node_role_dependencies" {
  description = "Values that must exist before the node group is created (IAM attachments)."
  type        = list(string)
  default     = []
}
