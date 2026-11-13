# cd terraform/modules/iam && terraform init && terraform test   (mock provider - no AWS calls)
mock_provider "aws" {
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_region" {
    defaults = { region = "ap-southeast-2" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
  }
}

variables {
  name                = "test"
  cluster_name        = "test"
  ecr_repository_arns = ["arn:aws:ecr:ap-southeast-2:123456789012:repository/test-backend"]
  db_secret_arn       = "arn:aws:secretsmanager:ap-southeast-2:123456789012:secret:rds-db-abc"
  github_repository   = "example-user/medicloud"
}

run "node_role_is_least_privilege" {
  command = apply

  assert {
    condition     = contains(keys(aws_iam_role_policy_attachment.node), "AmazonEC2ContainerRegistryPullOnly")
    error_message = "Nodes get ECR pull-only access."
  }
  assert {
    condition     = !contains(keys(aws_iam_role_policy_attachment.node), "AmazonEC2ContainerRegistryReadOnly")
    error_message = "The broader ReadOnly policy must not be used."
  }
}

run "github_role_trusts_one_repo_and_environment" {
  command = apply

  assert {
    condition = one([
      for c in data.aws_iam_policy_document.github_assume[0].statement[0].condition :
      c.values[0] if c.variable == "token.actions.githubusercontent.com:sub"
    ]) == "repo:example-user/medicloud:environment:production"
    error_message = "Only the production environment of this repository may assume the role."
  }
  assert {
    condition = one([
      for c in data.aws_iam_policy_document.github_assume[0].statement[0].condition :
      c.test if c.variable == "token.actions.githubusercontent.com:sub"
    ]) == "StringEquals"
    error_message = "The subject must match exactly (no wildcards)."
  }
  assert {
    condition = one([
      for s in data.aws_iam_policy_document.github_deploy[0].statement :
      s.resources if s.sid == "DescribeOneCluster"
    ]) == toset(["arn:aws:eks:ap-southeast-2:123456789012:cluster/test"])
    error_message = "The deploy role may describe only this cluster."
  }
  assert {
    condition = one([
      for s in data.aws_iam_policy_document.github_deploy[0].statement :
      s.resources if s.sid == "EcrPushPullOwnRepositories"
    ]) == toset(["arn:aws:ecr:ap-southeast-2:123456789012:repository/test-backend"])
    error_message = "ECR push is limited to the project's repositories."
  }
}

run "github_role_trusts_immutable_repository_ids" {
  command = apply
  variables {
    github_owner_id      = "1111"
    github_repository_id = "2222"
  }

  # GitHub sends "owner@id/repo@id" for repositories that use immutable identifiers.
  assert {
    condition = one([
      for c in data.aws_iam_policy_document.github_assume[0].statement[0].condition :
      c.values[0] if c.variable == "token.actions.githubusercontent.com:sub"
    ]) == "repo:example-user@1111/medicloud@2222:environment:production"
    error_message = "With IDs set, the subject must pin the owner and repository IDs exactly."
  }
}

run "no_ci_iam_without_repository" {
  command = plan
  variables {
    github_repository = ""
  }

  assert {
    condition     = length(aws_iam_role.github_deploy) == 0 && length(aws_iam_openid_connect_provider.github) == 0
    error_message = "No OIDC provider or deploy role may exist when CI/CD is disabled."
  }
}
