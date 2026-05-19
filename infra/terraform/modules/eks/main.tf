# ─────────────────────────────────────────────────────────────────────────────
# EKS Module — Managed Kubernetes cluster with auto-scaling node groups
# ─────────────────────────────────────────────────────────────────────────────

variable "project_name" { type = string }
variable "environment" { type = string }
variable "cluster_version" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "node_instance_types" { type = list(string) }
variable "node_desired_size" { type = number }
variable "node_min_size" { type = number }
variable "node_max_size" { type = number }
variable "node_disk_size" { type = number }
variable "cluster_role_arn" { type = string }
variable "node_role_arn" { type = string }
variable "allowed_cidr_blocks" {
  type    = list(string)
  default = ["10.0.0.0/8"]
}

locals {
  name_prefix  = "${var.project_name}-${var.environment}"
  cluster_name = "${local.name_prefix}-eks"
}

data "aws_caller_identity" "current" {}

# ── EKS Cluster ───────────────────────────────────────────────────────────────

resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = var.cluster_role_arn

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
    security_group_ids      = [aws_security_group.cluster.id]
  }

  encryption_config {
    provider { key_arn = aws_kms_key.eks.arn }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api", "audit", "authenticator", "controllerManager", "scheduler"
  ]

  tags = { Name = local.cluster_name }
}

# ── KMS Key for Secrets Encryption ────────────────────────────────────────────

resource "aws_kms_key" "eks" {
  description             = "EKS secrets encryption key for ${local.cluster_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "eks-key-policy"
    Statement = [
      {
        Sid       = "EnableRootAccountAccess"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      }
    ]
  })

  tags = { Name = "${local.cluster_name}-kms" }
}

# ── Managed Node Group ────────────────────────────────────────────────────────

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.name_prefix}-general"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.node_instance_types
  disk_size       = var.node_disk_size
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role        = "general"
    environment = var.environment
  }

  tags = { Name = "${local.name_prefix}-node-group" }
}

# Spot node group for non-critical workloads
resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.name_prefix}-spot"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = ["m6i.large", "m6a.large", "m5.large"]
  capacity_type   = "SPOT"

  scaling_config {
    desired_size = 2
    min_size     = 0
    max_size     = 8
  }

  labels = {
    role        = "spot-workers"
    environment = var.environment
  }

  taint {
    key    = "spot"
    value  = "true"
    effect = "PREFER_NO_SCHEDULE"
  }

  tags = { Name = "${local.name_prefix}-spot-group" }
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "cluster" {
  name_prefix = "${local.name_prefix}-eks-"
  vpc_id      = var.vpc_id
  description = "EKS cluster security group for ${local.cluster_name}"

  tags = { Name = "${local.name_prefix}-eks-sg" }
}

resource "aws_security_group_rule" "cluster_ingress_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  self              = true
  security_group_id = aws_security_group.cluster.id
  description       = "Allow HTTPS from within cluster"
}

resource "aws_security_group_rule" "cluster_egress_https" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.cluster.id
  description       = "Allow HTTPS outbound for AWS APIs"
}

resource "aws_security_group_rule" "cluster_egress_dns_tcp" {
  type              = "egress"
  from_port         = 53
  to_port           = 53
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.cluster.id
  description       = "Allow DNS TCP outbound"
}

resource "aws_security_group_rule" "cluster_egress_dns_udp" {
  type              = "egress"
  from_port         = 53
  to_port           = 53
  protocol          = "udp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.cluster.id
  description       = "Allow DNS UDP outbound"
}

resource "aws_security_group_rule" "cluster_egress_nodes" {
  type              = "egress"
  from_port         = 1025
  to_port           = 65535
  protocol          = "tcp"
  self              = true
  security_group_id = aws_security_group.cluster.id
  description       = "Allow communication to worker nodes"
}

# ── EKS Addons ────────────────────────────────────────────────────────────────

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
  depends_on   = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "aws-ebs-csi-driver"
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "cluster_name" { value = aws_eks_cluster.main.name }
output "cluster_endpoint" { value = aws_eks_cluster.main.endpoint }
output "cluster_ca_certificate" { value = aws_eks_cluster.main.certificate_authority[0].data }
output "cluster_security_group_id" { value = aws_security_group.cluster.id }
output "oidc_issuer" { value = aws_eks_cluster.main.identity[0].oidc[0].issuer }
