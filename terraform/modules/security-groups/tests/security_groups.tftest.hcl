# cd terraform/modules/security-groups && terraform init && terraform test   (mock provider)
mock_provider "aws" {}

variables {
  name                          = "test"
  vpc_id                        = "vpc-123"
  eks_cluster_security_group_id = "sg-eks-cluster"
}

run "postgres_reachable_only_from_eks" {
  command = apply

  assert {
    condition     = aws_vpc_security_group_ingress_rule.rds_from_eks.referenced_security_group_id == "sg-eks-cluster"
    error_message = "PostgreSQL must accept traffic only from the EKS cluster security group."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.rds_from_eks.cidr_ipv4 == null
    error_message = "No CIDR-based (e.g. internet) access to the database."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.rds_from_eks.from_port == 5432 && aws_vpc_security_group_ingress_rule.rds_from_eks.to_port == 5432
    error_message = "Only the PostgreSQL port may be opened."
  }
}
