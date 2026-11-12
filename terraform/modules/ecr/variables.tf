variable "repositories" {
  description = "Repository names to create."
  type        = list(string)
}

variable "force_delete" {
  description = "Allow deleting repositories that still contain images."
  type        = bool
  default     = false
}
