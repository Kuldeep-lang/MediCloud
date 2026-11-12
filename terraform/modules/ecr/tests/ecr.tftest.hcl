# cd terraform/modules/ecr && terraform init && terraform test   (mock provider - no AWS calls)
mock_provider "aws" {}

variables {
  repositories = ["test-backend", "test-frontend"]
}

run "repositories_are_immutable_and_scanned" {
  command = apply

  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_tag_mutability == "IMMUTABLE"])
    error_message = "Tags must be immutable so a deployed tag can never change underneath you."
  }
  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_scanning_configuration[0].scan_on_push])
    error_message = "Every pushed image must be scanned."
  }
  assert {
    condition     = length(aws_ecr_lifecycle_policy.this) == 2
    error_message = "Each repository needs a lifecycle policy to bound storage cost."
  }
  assert {
    condition     = length(jsondecode(aws_ecr_lifecycle_policy.this["test-backend"].policy).rules) == 2
    error_message = "Lifecycle: expire untagged images and keep the last 10."
  }
}
