# One-time bootstrap: the S3 bucket that holds the main stack's remote state.
# This tiny configuration keeps its own state locally (terraform/bootstrap/terraform.tfstate,
# git-ignored) - a remote backend cannot store the state of the bucket that hosts it.
#
#   cd terraform/bootstrap && terraform init && terraform apply
#
# Cost: an S3 bucket holding a few KB of state - fractions of a cent per month.

terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = var.project_name, ManagedBy = "terraform", Purpose = "terraform-state" }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # Bucket names are global: include the account ID so the name is unique.
  bucket_name = "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"
}

#trivy:ignore:AWS-0089 Access logging would need a second bucket; state access is already authenticated, TLS-only and versioned.
resource "aws_s3_bucket" "state" {
  bucket = local.bucket_name

  # Allow `terraform destroy` here only after the main stack is gone and the bucket emptied.
  force_destroy = false
}

# Every state change is kept - an accidental corruption can be rolled back.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

#trivy:ignore:AWS-0132 SSE-S3 (AES-256) encrypts state at rest; no secrets are stored in state (RDS password is managed by Secrets Manager), so a $1/month CMK is not justified.
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs disabled
  }
}

# Refuse any request that is not over TLS.
data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.state.arn,
      "${aws_s3_bucket.state.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}

# Old state versions are useful for a while, not forever.
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
