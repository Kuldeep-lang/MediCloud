terraform {
  # 1.10+ is required for S3-native state locking (use_lockfile) - see backend.tf.example.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }
}
