# Unit tests with a MOCK AWS provider: no credentials, no AWS calls, no cost.
#   cd terraform/modules/vpc && terraform init && terraform test
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"] }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  # Real AWS returns a JSON document; the provider validates it on aws_iam_role.
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  # aws_flow_log validates that these are well-formed ARNs.
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:ap-southeast-2:123456789012:log-group:/aws/vpc/test/flow-logs" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/test-vpc-flow-logs" }
  }
}

variables {
  name         = "test"
  cidr_block   = "10.20.0.0/16"
  az_count     = 2
  cluster_name = "test"
}

run "subnet_layout_and_routing" {
  command = apply

  assert {
    condition     = [for s in aws_subnet.public : s.cidr_block] == ["10.20.0.0/24", "10.20.1.0/24"]
    error_message = "Public subnets must be one /24 per AZ."
  }
  assert {
    condition     = [for s in aws_subnet.private : s.cidr_block] == ["10.20.16.0/20", "10.20.32.0/20"]
    error_message = "Private subnets must be one /20 per AZ (room for VPC CNI pod IPs)."
  }
  assert {
    condition     = [for s in aws_subnet.private : s.availability_zone] == ["ap-southeast-2a", "ap-southeast-2b"]
    error_message = "Subnets must spread across distinct AZs."
  }
  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch == false])
    error_message = "Nothing may receive a public IP automatically."
  }
  assert {
    condition     = aws_route.private_nat.destination_cidr_block == "0.0.0.0/0" && aws_route.private_nat.nat_gateway_id == aws_nat_gateway.this.id
    error_message = "Private subnets must egress only through the NAT gateway."
  }
  assert {
    condition     = alltrue([for s in aws_subnet.public : s.tags["kubernetes.io/role/elb"] == "1"])
    error_message = "Public subnets need the ELB discovery tag for internet-facing load balancers."
  }
}

run "flow_logs_capture_rejects" {
  command = apply

  assert {
    condition     = aws_flow_log.this[0].traffic_type == "REJECT" && aws_cloudwatch_log_group.flow_logs[0].retention_in_days == 3
    error_message = "Flow logs must record REJECTed traffic with short retention."
  }
}

run "flow_logs_can_be_disabled" {
  command = plan
  variables {
    enable_flow_logs = false
  }

  assert {
    condition     = length(aws_flow_log.this) == 0 && length(aws_iam_role.flow_logs) == 0
    error_message = "Disabling flow logs must remove the log group, role and flow log."
  }
}

run "single_az_is_rejected" {
  command = plan
  variables {
    az_count = 1
  }
  expect_failures = [var.az_count]
}
