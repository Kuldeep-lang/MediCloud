output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.host.id
}

output "public_ip" {
  description = "Public IPv4 address (SSH for Ansible, HTTP for users)."
  value       = aws_instance.host.public_ip
}

output "private_ip" {
  description = "Private IPv4 address (Prometheus in EKS scrapes node_exporter here)."
  value       = aws_instance.host.private_ip
}

output "security_group_id" {
  description = "Security group of the host."
  value       = aws_security_group.host.id
}
