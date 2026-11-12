# Amazon RDS for PostgreSQL 17 (same major version as local Docker/Kubernetes).
#
#   - private subnets only, publicly_accessible = false, reachable from EKS only (SG)
#   - storage encrypted; TLS enforced (rds.force_ssl = 1)
#   - manage_master_user_password: RDS generates the password and stores it in Secrets
#     Manager - it never appears in Terraform code, variables or state
#   - cost-conscious demo defaults: db.t4g.micro, single-AZ, 20 GiB gp3, 1-day backups,
#     no deletion protection / final snapshot so `terraform destroy` is clean

resource "aws_db_subnet_group" "this" {
  name        = "${var.name}-db"
  description = "Private subnets for ${var.name} PostgreSQL"
  subnet_ids  = var.subnet_ids
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name}-pg${var.engine_version}-"
  family      = "postgres${var.engine_version}"
  description = "${var.name} PostgreSQL ${var.engine_version} parameters"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
    # AWS records this parameter as pending-reboot; declaring the same avoids a perpetual
    # diff. A new instance gets the value at creation, so TLS is enforced from the start.
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # log queries slower than 1 s
  }

  lifecycle {
    create_before_destroy = true
  }
}

#trivy:ignore:AWS-0177 Deletion protection is a variable, off by default so the demo can be destroyed the same day (cost control).
#trivy:ignore:AWS-0133 Performance Insights is not needed for a db.t4g.micro demo and is superseded by CloudWatch Database Insights.
#trivy:ignore:AWS-0077 Retention is a variable; the root default is 1 day because AWS Free-plan accounts reject more (D38). Set 7 on a Paid plan.
resource "aws_db_instance" "this" {
  identifier     = "${var.name}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name                     = "medicloud"
  username                    = "medicloud_admin"
  manage_master_user_password = true

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.security_group_ids
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false
  multi_az               = var.multi_az
  ca_cert_identifier     = "rds-ca-rsa2048-g1"

  iam_database_authentication_enabled = true
  auto_minor_version_upgrade          = true
  apply_immediately                   = true

  backup_retention_period = var.backup_retention_period
  backup_window           = "17:00-17:30" # UTC = 22:30-23:00 IST
  maintenance_window      = "sun:18:00-sun:18:30"
  copy_tags_to_snapshot   = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-postgres-final"
}
