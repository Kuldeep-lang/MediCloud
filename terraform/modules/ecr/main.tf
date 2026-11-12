# Container registries. Tags are IMMUTABLE: CI tags every image with its git commit SHA,
# so a tag always means exactly one build (no silent overwrites of what is deployed).

#trivy:ignore:AWS-0033 Images are encrypted at rest with AES-256; a customer-managed KMS key adds cost without benefit for public-source images.
resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name                 = each.key
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true # second opinion next to the Trivy scan in CI
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Keep storage cost flat: drop untagged layers quickly and keep the last 10 releases.
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the 10 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
