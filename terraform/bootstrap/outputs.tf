output "state_bucket" {
  description = "Put this name in terraform/backend.tf (copied from backend.tf.example)."
  value       = aws_s3_bucket.state.bucket
}
