variable "aws_region" {
  description = "Region for the state bucket (use the same region as the main stack)."
  type        = string
  default     = "ap-southeast-2"
}

variable "project_name" {
  description = "Prefix for the bucket name."
  type        = string
  default     = "medicloud"
}
