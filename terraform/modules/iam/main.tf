# IAM for MediCloud, least privilege throughout:
#   - EKS cluster role : only AmazonEKSClusterPolicy
#   - node role        : worker + VPC CNI policies; ECR *pull-only* (not ReadOnly)
#   - GitHub deploy role (optional): assumed via OIDC - no long-lived keys anywhere.
#     Trusts ONE repository AND ONE GitHub Environment; can push to the two ECR repos,
#     describe ONE cluster and read ONE secret. Kubernetes permissions are granted
#     separately (namespace-scoped) by an EKS access entry in the eks module.

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  partition       = data.aws_partition.current.partition
  account_id      = data.aws_caller_identity.current.account_id
  cluster_arn     = "arn:${local.partition}:eks:${data.aws_region.current.region}:${local.account_id}:cluster/${var.cluster_name}"
  enable_github   = var.github_repository != ""
  github_oidc_url = "token.actions.githubusercontent.com"
}

# ---------------------------------------------------------------- EKS cluster role
data "aws_iam_policy_document" "eks_assume" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.name}-eks-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_assume.json
}

resource "aws_iam_role_policy_attachment" "cluster" {
  for_each = toset(["AmazonEKSClusterPolicy"])

  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/${each.key}"
}

# ---------------------------------------------------------------- node role
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.name}-eks-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryPullOnly",
  ])

  role       = aws_iam_role.node.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/${each.key}"
}

# ---------------------------------------------------------------- GitHub Actions (OIDC)
resource "aws_iam_openid_connect_provider" "github" {
  count = local.enable_github && var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = local.enable_github && !var.create_github_oidc_provider ? 1 : 0
  url   = "https://${local.github_oidc_url}"
}

locals {
  github_oidc_arn = local.enable_github ? (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : data.aws_iam_openid_connect_provider.github[0].arn
  ) : null
}

data "aws_iam_policy_document" "github_assume" {
  count = local.enable_github ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs running in the protected GitHub Environment of THIS repository.
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count = local.enable_github ? 1 : 0

  name                 = "${var.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_assume[0].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  count = local.enable_github ? 1 : 0

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this action does not support resource-level scoping
  }

  statement {
    sid = "EcrPushPullOwnRepositories"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = var.ecr_repository_arns
  }

  statement {
    sid       = "DescribeOneCluster"
    actions   = ["eks:DescribeCluster"]
    resources = [local.cluster_arn]
  }

  statement {
    sid       = "ReadDatabaseSecret"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [var.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count = local.enable_github ? 1 : 0

  name   = "${var.name}-github-deploy"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy[0].json
}
