variable "name" {
  description = "Name prefix for every resource."
  type        = string
}

variable "vpc_id" {
  description = "VPC to place the host in."
  type        = string
}

variable "subnet_id" {
  description = "Public subnet for the host (it needs a public IP for SSH and HTTP)."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type. t3.small (2 GiB) is Free-plan eligible and fits the Compose stack."
  type        = string
  default     = "t3.small"
}

variable "root_volume_size" {
  description = "Root disk size in GiB (OS + Docker images + PostgreSQL data)."
  type        = number
  default     = 20
}

variable "ssh_public_key" {
  description = "OpenSSH public key that Ansible uses to log in as the 'ubuntu' user."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) ", var.ssh_public_key))
    error_message = "ssh_public_key must be an OpenSSH public key (ssh-ed25519 ..., ssh-rsa ...)."
  }
}

variable "ssh_ingress_cidrs" {
  description = "CIDRs allowed to SSH (port 22). Keep this to the operator's own /32."
  type        = list(string)

  validation {
    condition     = length(var.ssh_ingress_cidrs) > 0 && alltrue([for c in var.ssh_ingress_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0"])
    error_message = "Give at least one valid CIDR, and never 0.0.0.0/0 for SSH."
  }
}

variable "ssh_ports" {
  description = "Ports sshd listens on. 443 is a fallback for networks (e.g. campus Wi-Fi) that block outbound 22."
  type        = list(number)
  default     = [22, 443]
}

variable "http_ingress_cidrs" {
  description = "CIDRs allowed to reach the web app on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_metrics_ingress" {
  description = "Allow metrics_source_security_group_id to scrape node_exporter on 9100."
  type        = bool
  default     = false
}

variable "metrics_source_security_group_id" {
  description = "Security group (the EKS cluster SG) allowed to scrape node_exporter when enable_metrics_ingress is true."
  type        = string
  default     = ""
}
