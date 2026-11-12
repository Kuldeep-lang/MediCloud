# Whole-stack plan test (mock AWS provider, no account needed).
#   cd terraform && terraform test
#
# Module tests check each module alone. This one plans the ROOT configuration with every
# optional feature on, the way a real session builds it from nothing. It catches errors
# that only appear when modules are wired together, such as a `count` that depends on an
# attribute of a resource created in the same apply ("Invalid count argument").

mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"]
    }
  }
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }
  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }
  mock_data "aws_region" {
    defaults = {
      region = "ap-southeast-2"
    }
  }
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }
  mock_resource "aws_launch_template" {
    defaults = {
      id = "lt-0123456789abcdef0"
    }
  }
}

variables {
  github_repository       = "example-owner/medicloud"
  enable_app_host         = true
  app_host_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyOnlyForTests ansible"
  app_host_ssh_cidrs      = ["203.0.113.10/32"]
}

run "full_stack_plans_from_scratch" {
  command = plan

  assert {
    condition     = length(module.app_host) == 1
    error_message = "The Ansible-managed VM must be planned when enable_app_host is true."
  }
  assert {
    condition     = output.cluster_name == "medicloud"
    error_message = "The cluster is named after the project."
  }
}

run "optional_features_off_by_default" {
  command = plan

  variables {
    github_repository       = ""
    enable_app_host         = false
    app_host_ssh_public_key = ""
    app_host_ssh_cidrs      = []
  }

  assert {
    condition     = length(module.app_host) == 0
    error_message = "No VM unless enable_app_host is true."
  }
  assert {
    condition     = output.github_deploy_role_arn == null
    error_message = "No CI/CD role without a GitHub repository."
  }
}
