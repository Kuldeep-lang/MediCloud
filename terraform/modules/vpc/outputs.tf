output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (NAT gateway, internet-facing load balancers)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS nodes, RDS)."
  value       = aws_subnet.private[*].id
}

output "azs" {
  description = "Availability zones in use."
  value       = local.azs
}

output "nat_public_ip" {
  description = "Elastic IP of the NAT gateway."
  value       = aws_eip.nat.public_ip
}
