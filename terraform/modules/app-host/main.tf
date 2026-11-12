# A single Ubuntu 24.04 VM that Ansible configures (Phase 6): Docker, node_exporter and the
# MediCloud Compose stack using images pulled from ECR. It complements the EKS deployment
# and shows configuration management of a classic server.

data "aws_partition" "current" {}

# Canonical publishes the current Ubuntu 24.04 LTS AMI ID as a public SSM parameter.
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_key_pair" "ansible" {
  key_name   = "${var.name}-ansible"
  public_key = var.ssh_public_key
}

# ---------------------------------------------------------------- network access
resource "aws_security_group" "host" {
  name_prefix = "${var.name}-app-host-"
  description = "MediCloud app host: SSH from the operator, HTTP from users"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${var.name}-app-host" }
}

locals {
  # One rule per (operator CIDR, ssh port) pair, e.g. "203.0.113.10/32:443".
  ssh_rules = { for pair in setproduct(var.ssh_ingress_cidrs, var.ssh_ports) : "${pair[0]}:${pair[1]}" => {
    cidr = pair[0]
    port = pair[1]
  } }
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each = local.ssh_rules

  security_group_id = aws_security_group.host.id
  description       = "SSH for Ansible (operator IP only)"
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
  cidr_ipv4         = each.value.cidr
}

#trivy:ignore:AWS-0107 Port 80 is the public web app; it is the only port open to the internet.
resource "aws_vpc_security_group_ingress_rule" "http" {
  for_each = toset(var.http_ingress_cidrs)

  security_group_id = aws_security_group.host.id
  description       = "MediCloud web app"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_ingress_rule" "node_exporter" {
  count = var.metrics_source_security_group_id == "" ? 0 : 1

  security_group_id            = aws_security_group.host.id
  description                  = "Prometheus in EKS scrapes node_exporter"
  ip_protocol                  = "tcp"
  from_port                    = 9100
  to_port                      = 9100
  referenced_security_group_id = var.metrics_source_security_group_id
}

#trivy:ignore:AWS-0104 The host must reach apt mirrors, download.docker.com, GitHub releases and ECR over HTTPS; there is no egress proxy in this design.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.host.id
  description       = "Package repositories, ECR, GitHub releases"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# ---------------------------------------------------------------- instance role (ECR pull only)
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name}-app-host"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ecr_pull" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly"
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name}-app-host"
  role = aws_iam_role.host.name
}

# ---------------------------------------------------------------- the VM
#trivy:ignore:AWS-0009 The host serves the web app directly and is reached by Ansible over SSH, so it needs a public IP; only ports 22 (operator /32) and 80 are open.
resource "aws_instance" "host" {
  ami                         = data.aws_ssm_parameter.ubuntu.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.host.id]
  key_name                    = aws_key_pair.ansible.key_name
  iam_instance_profile        = aws_iam_instance_profile.host.name
  associate_public_ip_address = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # containers can't reach the instance role
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
  }

  credit_specification {
    cpu_credits = "standard" # never bill for burst credits beyond the baseline
  }

  # sshd also listens on the fallback ports from first boot, so Ansible can connect even
  # from a network that blocks outbound 22. Ubuntu 24.04 uses socket activation: after
  # changing Port, systemd must regenerate ssh.socket.
  user_data = "#cloud-config\n${yamlencode({
    write_files = [{
      path        = "/etc/ssh/sshd_config.d/10-medicloud-ports.conf"
      permissions = "0644"
      content     = join("", [for p in var.ssh_ports : "Port ${p}\n"])
    }]
    runcmd = [
      ["systemctl", "daemon-reload"],
      ["systemctl", "restart", "ssh.socket"],
    ]
  })}"

  # A new AMI release must not replace a configured host mid-session.
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  tags = {
    Name = "${var.name}-app-host"
    Role = "app-server" # Ansible's dynamic inventory selects hosts by this tag
  }
}
