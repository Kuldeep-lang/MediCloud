# Credentials are NEVER configured here. Terraform uses the standard AWS credential chain:
#   - locally: your AWS CLI profile / SSO session (aws configure, aws sso login)
#   - in CI:   short-lived credentials from GitHub OIDC (aws-actions/configure-aws-credentials)
provider "aws" {
  region = var.aws_region

  # Every resource is tagged - Cost Explorer can then show exactly what MediCloud cost,
  # and scripts/aws-leftovers.sh can find anything left behind after a destroy.
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
