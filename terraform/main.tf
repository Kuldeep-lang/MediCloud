# MediCloud on AWS
#
#   VPC (2 AZs: public + private subnets, one NAT gateway)
#    ├─ EKS cluster + managed node group (private subnets)
#    └─ RDS PostgreSQL (private subnets, reachable only from the EKS security group)
#   ECR repositories, IAM roles (incl. GitHub OIDC deploy role), optional AWS Budget
#
# Resource-level dependencies flow between modules; there are no cycles:
#   iam(cluster/node roles) -> eks -> security_groups -> rds -> iam(deploy policy)

locals {
  name = var.project_name
}

module "vpc" {
  source = "./modules/vpc"

  name         = local.name
  cidr_block   = var.vpc_cidr
  az_count     = var.az_count
  cluster_name = local.name

  enable_flow_logs = var.enable_vpc_flow_logs
}

module "ecr" {
  source = "./modules/ecr"

  repositories = var.ecr_repositories
  force_delete = var.ecr_force_delete
}

module "iam" {
  source = "./modules/iam"

  name                        = local.name
  cluster_name                = local.name
  ecr_repository_arns         = module.ecr.repository_arns
  db_secret_arn               = module.rds.master_user_secret_arn
  github_repository           = var.github_repository
  github_environment          = var.github_environment
  create_github_oidc_provider = var.create_github_oidc_provider
}

module "eks" {
  source = "./modules/eks"

  name                = local.name
  kubernetes_version  = var.kubernetes_version
  cluster_role_arn    = module.iam.cluster_role_arn
  node_role_arn       = module.iam.node_role_arn
  subnet_ids          = module.vpc.private_subnet_ids
  public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  cluster_log_types   = var.cluster_log_types
  instance_types      = var.node_instance_types
  capacity_type       = var.node_capacity_type
  desired_size        = var.node_desired_size
  min_size            = var.node_min_size
  max_size            = var.node_max_size
  deploy_role_arn     = module.iam.github_deploy_role_arn
  # known at plan time, unlike the role ARN
  enable_deploy_access = var.github_repository != ""

  # Policies must be attached before the cluster/nodes use the roles.
  cluster_role_dependencies = module.iam.cluster_role_policy_attachments
  node_role_dependencies    = module.iam.node_role_policy_attachments
}

module "security_groups" {
  source = "./modules/security-groups"

  name                          = local.name
  vpc_id                        = module.vpc.vpc_id
  eks_cluster_security_group_id = module.eks.cluster_security_group_id
}

module "rds" {
  source = "./modules/rds"

  name                    = local.name
  subnet_ids              = module.vpc.private_subnet_ids
  security_group_ids      = [module.security_groups.rds_security_group_id]
  instance_class          = var.db_instance_class
  engine_version          = var.db_engine_version
  allocated_storage       = var.db_allocated_storage
  multi_az                = var.db_multi_az
  backup_retention_period = var.db_backup_retention_days
  deletion_protection     = var.db_deletion_protection
  skip_final_snapshot     = var.db_skip_final_snapshot
}

# ---------------------------------------------------------------- Ansible-managed VM (Phase 6)
module "app_host" {
  source = "./modules/app-host"
  count  = var.enable_app_host ? 1 : 0

  name                             = local.name
  vpc_id                           = module.vpc.vpc_id
  subnet_id                        = module.vpc.public_subnet_ids[0]
  instance_type                    = var.app_host_instance_type
  ssh_public_key                   = var.app_host_ssh_public_key
  ssh_ingress_cidrs                = var.app_host_ssh_cidrs
  enable_metrics_ingress           = true
  metrics_source_security_group_id = module.eks.cluster_security_group_id
}

# ---------------------------------------------------------------- cost guardrail
resource "aws_budgets_budget" "monthly" {
  count = var.budget_alert_email == "" ? 0 : 1

  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [25, 50, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_alert_email]
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
