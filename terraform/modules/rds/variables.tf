variable "name" {
  description = "Name prefix."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets (at least two AZs) for the DB subnet group."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups for the instance."
  type        = list(string)
}

variable "instance_class" {
  description = "Instance class."
  type        = string
}

variable "engine_version" {
  description = "PostgreSQL major version, e.g. 17."
  type        = string
}

variable "allocated_storage" {
  description = "Storage in GiB."
  type        = number
}

variable "multi_az" {
  description = "Create a standby in another AZ."
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "Days of automated backups."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Prevent deletion."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on delete."
  type        = bool
  default     = true
}
