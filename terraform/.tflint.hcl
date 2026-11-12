# TFLint: catches what `terraform validate` cannot (invalid instance types, deprecated
# syntax, unused declarations, missing docs/types).
#   docker run --rm -v "$PWD:/data" -w /data ghcr.io/terraform-linters/tflint:v0.65.0 --init
#   docker run --rm -v "$PWD:/data" -w /data ghcr.io/terraform-linters/tflint:v0.65.0 --recursive
config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.50.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
