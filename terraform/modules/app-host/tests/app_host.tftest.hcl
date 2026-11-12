# Offline tests (mock provider): security properties of the Ansible-managed VM.
#   cd terraform/modules/app-host && terraform init && terraform test

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }
}

variables {
  name              = "medicloud"
  vpc_id            = "vpc-123"
  subnet_id         = "subnet-public-a"
  ssh_public_key    = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyOnlyForTests ansible"
  ssh_ingress_cidrs = ["203.0.113.10/32"]
}

run "hardened_instance" {
  command = plan

  assert {
    condition     = aws_instance.host.metadata_options[0].http_tokens == "required"
    error_message = "IMDSv2 must be required."
  }
  assert {
    condition     = aws_instance.host.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Hop limit must be 1 so containers cannot reach the instance role."
  }
  assert {
    condition     = aws_instance.host.root_block_device[0].encrypted == true
    error_message = "Root volume must be encrypted."
  }
  assert {
    condition     = aws_instance.host.tags["Role"] == "app-server"
    error_message = "The Role tag drives Ansible's dynamic inventory."
  }
  assert {
    condition     = aws_instance.host.credit_specification[0].cpu_credits == "standard"
    error_message = "Burst credits must not be billed (standard mode)."
  }
}

run "least_privilege_network_and_iam" {
  command = plan

  assert {
    condition     = toset(keys(aws_vpc_security_group_ingress_rule.ssh)) == toset(["203.0.113.10/32:22", "203.0.113.10/32:443"])
    error_message = "SSH (22 and the 443 fallback) must be open only to the operator CIDR."
  }
  assert {
    condition     = strcontains(aws_instance.host.user_data, "Port 443")
    error_message = "sshd must also listen on the fallback port."
  }
  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.node_exporter) == 0
    error_message = "node_exporter must stay closed unless a scraper security group is given."
  }
  assert {
    condition     = endswith(aws_iam_role_policy_attachment.ecr_pull.policy_arn, "policy/AmazonEC2ContainerRegistryPullOnly")
    error_message = "The instance role may only pull from ECR."
  }
}

run "rejects_world_open_ssh" {
  command = plan

  variables {
    ssh_ingress_cidrs = ["0.0.0.0/0"]
  }

  expect_failures = [var.ssh_ingress_cidrs]
}
