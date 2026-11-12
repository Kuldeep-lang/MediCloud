# Amazon EKS: control plane + one managed node group + managed add-ons.
#
# Security and cost decisions:
#   - authentication_mode = API: access via EKS access entries (no aws-auth ConfigMap)
#   - Kubernetes Secrets encrypted at rest with a dedicated KMS key
#   - upgrade_policy STANDARD: when a version leaves standard support, EKS upgrades it
#     instead of silently moving it to extended support (6x the hourly price)
#   - nodes in private subnets, IMDSv2 required with hop limit 1 (pods cannot reach the
#     node's instance metadata / IAM credentials), encrypted gp3 root volumes
#   - VPC CNI with network-policy enforcement, so k8s/09-policies.yaml is enforced on AWS
#   - CI/CD role mapped to edit ONLY the medicloud namespace

data "aws_partition" "current" {}

# Implicit dependency on the IAM policy attachments (passed in from the iam module).
resource "terraform_data" "cluster_role_ready" {
  input = var.cluster_role_dependencies
}

resource "terraform_data" "node_role_ready" {
  input = var.node_role_dependencies
}

# ---------------------------------------------------------------- logging + encryption
#trivy:ignore:AWS-0017 Default encryption at rest; a CMK ($1/month) is not justified for 3-day demo logs.
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.name}/cluster"
  retention_in_days = 3 # demo: keep log storage cost negligible
}

resource "aws_kms_key" "secrets" {
  description             = "${var.name} EKS secrets envelope encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.name}-eks-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# AmazonEKSClusterPolicy does not cover KMS: allow the control plane to use THIS key only.
data "aws_iam_policy_document" "cluster_kms" {
  statement {
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:ListGrants", "kms:DescribeKey"]
    resources = [aws_kms_key.secrets.arn]
  }
}

resource "aws_iam_role_policy" "cluster_kms" {
  name   = "${var.name}-eks-secrets-kms"
  role   = element(split("/", var.cluster_role_arn), length(split("/", var.cluster_role_arn)) - 1)
  policy = data.aws_iam_policy_document.cluster_kms.json
}

# ---------------------------------------------------------------- control plane
#trivy:ignore:AWS-0038 audit + authenticator logs are enabled (who did what, who logged in); verbose api/scheduler/controllerManager logs are optional via var.cluster_log_types to limit CloudWatch cost.
#trivy:ignore:AWS-0040 Public endpoint is a decided trade-off (D37): GitHub-hosted runners deploy from changing IPs. Every request still needs IAM authentication plus an EKS access entry.
#trivy:ignore:AWS-0041 Default 0.0.0.0/0 is a decided trade-off (D37) for the same reason; narrow it with var.public_access_cidrs when CI runs from fixed IPs.
resource "aws_eks_cluster" "this" {
  name     = var.name
  version  = var.kubernetes_version
  role_arn = var.cluster_role_arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true # nodes talk to the API inside the VPC
    endpoint_public_access  = true # kubectl / CI from outside, IAM-authenticated
    public_access_cidrs     = var.public_access_cidrs
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true # the identity running terraform
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.secrets.arn
    }
  }

  upgrade_policy {
    support_type = "STANDARD"
  }

  enabled_cluster_log_types = var.cluster_log_types

  # Add-ons below are EKS-managed (versioned and upgradable through the API).
  bootstrap_self_managed_addons = false

  depends_on = [
    terraform_data.cluster_role_ready,
    aws_iam_role_policy.cluster_kms,
    aws_cloudwatch_log_group.cluster,
  ]
}

# ---------------------------------------------------------------- add-ons (before nodes)
resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "vpc-cni"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  configuration_values        = jsonencode({ enableNetworkPolicy = "true" })
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "kube-proxy"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}

# ---------------------------------------------------------------- worker nodes
resource "aws_launch_template" "nodes" {
  name_prefix = "${var.name}-nodes-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # containers cannot reach IMDS
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.name}-node" }
  }
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-default"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = var.capacity_type
  instance_types  = var.instance_types

  launch_template {
    id      = aws_launch_template.nodes.id
    version = aws_launch_template.nodes.latest_version
  }

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = { workload = "general" }

  depends_on = [
    terraform_data.node_role_ready,
    aws_eks_addon.vpc_cni, # pod networking must exist before nodes join
    aws_eks_addon.kube_proxy,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size] # allow manual/auto scaling
  }
}

# ---------------------------------------------------------------- add-ons (need nodes)
resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [aws_eks_node_group.default]
}

# Community add-on: feeds the HorizontalPodAutoscaler in k8s/08-hpa.yaml.
resource "aws_eks_addon" "metrics_server" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "metrics-server"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [aws_eks_node_group.default]
}

# ---------------------------------------------------------------- CI/CD access (namespaced)
# count uses enable_deploy_access (known at plan time): the role ARN itself is unknown until
# the role is created in the same apply, which Terraform rejects as a count argument.
resource "aws_eks_access_entry" "deploy" {
  count = var.enable_deploy_access ? 1 : 0

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.deploy_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "deploy_edit_app" {
  count = var.enable_deploy_access ? 1 : 0

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.deploy_role_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["medicloud"]
  }

  depends_on = [aws_eks_access_entry.deploy]
}

# Read-only view of the ingress controller namespace (CD reads the load balancer hostname).
resource "aws_eks_access_policy_association" "deploy_view_ingress" {
  count = var.enable_deploy_access ? 1 : 0

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.deploy_role_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["nginx-ingress"]
  }

  depends_on = [aws_eks_access_entry.deploy]
}
