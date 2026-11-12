# cd terraform/modules/eks && terraform init && terraform test   (mock provider - no AWS calls)
mock_provider "aws" {
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:ap-southeast-2:123456789012:key/11111111-2222-3333-4444-555555555555" }
  }
  # The node group validates that launch template IDs look like real ones (lt-...).
  mock_resource "aws_launch_template" {
    defaults = { id = "lt-0123456789abcdef0", latest_version = 1 }
  }
}

variables {
  name                = "test"
  kubernetes_version  = "1.37"
  cluster_role_arn    = "arn:aws:iam::123456789012:role/test-eks-cluster"
  node_role_arn       = "arn:aws:iam::123456789012:role/test-eks-node"
  subnet_ids          = ["subnet-aaa", "subnet-bbb"]
  public_access_cidrs = ["203.0.113.10/32"]
  cluster_log_types   = ["audit", "authenticator"]
  instance_types      = ["t3.medium"]
  capacity_type       = "ON_DEMAND"
  desired_size        = 2
  min_size            = 1
  max_size            = 3
  deploy_role_arn     = "arn:aws:iam::123456789012:role/test-github-deploy"
}

run "cluster_security_and_cost_guards" {
  command = apply

  assert {
    condition     = aws_eks_cluster.this.upgrade_policy[0].support_type == "STANDARD"
    error_message = "Clusters must never drift into paid extended support."
  }
  assert {
    condition     = aws_eks_cluster.this.access_config[0].authentication_mode == "API"
    error_message = "Access must use EKS access entries, not the aws-auth ConfigMap."
  }
  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_private_access
    error_message = "Nodes must reach the API privately."
  }
  assert {
    condition     = one(aws_eks_cluster.this.encryption_config[0].resources) == "secrets"
    error_message = "Kubernetes Secrets must be envelope-encrypted with KMS."
  }
  assert {
    condition     = aws_iam_role_policy.cluster_kms.role == "test-eks-cluster"
    error_message = "The KMS permission must attach to the cluster role parsed from its ARN."
  }
}

run "nodes_are_hardened" {
  command = apply

  assert {
    condition     = aws_launch_template.nodes.metadata_options[0].http_tokens == "required"
    error_message = "IMDSv2 must be required."
  }
  assert {
    condition     = aws_launch_template.nodes.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Hop limit 1 keeps containers away from the node's IAM credentials."
  }
  assert {
    condition     = aws_launch_template.nodes.block_device_mappings[0].ebs[0].encrypted == "true"
    error_message = "Node root volumes must be encrypted."
  }
  assert {
    condition     = aws_eks_node_group.default.subnet_ids == toset(["subnet-aaa", "subnet-bbb"])
    error_message = "Nodes must run in the given (private) subnets."
  }
  assert {
    condition     = jsondecode(aws_eks_addon.vpc_cni.configuration_values).enableNetworkPolicy == "true"
    error_message = "The VPC CNI must enforce Kubernetes NetworkPolicies."
  }
}

run "ci_role_is_namespace_scoped" {
  command = apply

  assert {
    condition     = aws_eks_access_policy_association.deploy_edit_app[0].access_scope[0].type == "namespace"
    error_message = "CI must not receive cluster-wide permissions."
  }
  assert {
    condition     = aws_eks_access_policy_association.deploy_edit_app[0].access_scope[0].namespaces == toset(["medicloud"])
    error_message = "CI may edit only the medicloud namespace."
  }
  assert {
    condition     = endswith(aws_eks_access_policy_association.deploy_view_ingress[0].policy_arn, "AmazonEKSViewPolicy")
    error_message = "CI gets read-only access to the ingress namespace."
  }
}

run "no_ci_access_without_role" {
  command = plan
  variables {
    deploy_role_arn = null
  }

  assert {
    condition     = length(aws_eks_access_entry.deploy) == 0
    error_message = "No access entry may exist when CI/CD is disabled."
  }
}
