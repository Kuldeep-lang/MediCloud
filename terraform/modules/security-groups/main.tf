# Security group for RDS: PostgreSQL is reachable ONLY from the EKS cluster security group
# (managed nodes and pods use it). No CIDR ranges, no internet, and no egress rules -
# Terraform removes AWS's default allow-all egress, and the database never initiates traffic.

resource "aws_security_group" "rds" {
  name_prefix = "${var.name}-rds-"
  description = "PostgreSQL access from the ${var.name} EKS cluster only"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-rds" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_eks" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from EKS nodes and pods"
  referenced_security_group_id = var.eks_cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
