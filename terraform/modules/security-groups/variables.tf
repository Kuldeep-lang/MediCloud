variable "name" {
  description = "Name prefix."
  type        = string
}

variable "vpc_id" {
  description = "VPC for the security groups."
  type        = string
}

variable "eks_cluster_security_group_id" {
  description = "EKS cluster security group allowed to reach PostgreSQL."
  type        = string
}
