variable "name" {
  description = "Name prefix for resources."
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR block (/16 recommended)."
  type        = string
}

variable "az_count" {
  description = "Number of availability zones (2 or 3)."
  type        = number

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "EKS and RDS subnet groups need at least 2 AZs; this module supports 2 or 3."
  }
}

variable "enable_flow_logs" {
  description = "Log rejected traffic to CloudWatch (3-day retention)."
  type        = bool
  default     = true
}

variable "cluster_name" {
  description = "EKS cluster name, used in subnet discovery tags for load balancers."
  type        = string
}
