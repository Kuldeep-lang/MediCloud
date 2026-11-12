# cd terraform/modules/rds && terraform init && terraform test   (mock provider - no AWS calls)
mock_provider "aws" {}

variables {
  name               = "test"
  subnet_ids         = ["subnet-aaa", "subnet-bbb"]
  security_group_ids = ["sg-123"]
  instance_class     = "db.t4g.micro"
  engine_version     = "17"
  allocated_storage  = 20
}

run "database_is_private_encrypted_and_tls_only" {
  command = apply

  assert {
    condition     = aws_db_instance.this.publicly_accessible == false
    error_message = "The database must never be publicly accessible."
  }
  assert {
    condition     = aws_db_instance.this.storage_encrypted
    error_message = "Storage must be encrypted at rest."
  }
  assert {
    condition     = aws_db_instance.this.manage_master_user_password
    error_message = "The master password must be managed by Secrets Manager (never in state)."
  }
  assert {
    condition     = one([for p in aws_db_parameter_group.this.parameter : p.value if p.name == "rds.force_ssl"]) == "1"
    error_message = "TLS must be enforced (rds.force_ssl = 1)."
  }
  assert {
    condition     = aws_db_parameter_group.this.family == "postgres17" && aws_db_instance.this.engine_version == "17"
    error_message = "PostgreSQL 17 must match the local Docker/Kubernetes version."
  }
  assert {
    condition     = aws_db_instance.this.vpc_security_group_ids == toset(["sg-123"])
    error_message = "Only the provided security group may be attached."
  }
}

run "demo_defaults_allow_clean_teardown" {
  command = plan

  assert {
    condition     = aws_db_instance.this.skip_final_snapshot && !aws_db_instance.this.deletion_protection
    error_message = "Demo defaults must allow terraform destroy without leaving paid snapshots."
  }
  assert {
    condition     = aws_db_instance.this.backup_retention_period == 7 && aws_db_instance.this.multi_az == false
    error_message = "Defaults: 7-day backups (free) and single-AZ (cost)."
  }
}

run "final_snapshot_named_when_kept" {
  command = plan
  variables {
    skip_final_snapshot = false
  }

  assert {
    condition     = aws_db_instance.this.final_snapshot_identifier == "test-postgres-final"
    error_message = "A final snapshot identifier is required when snapshots are kept."
  }
}
