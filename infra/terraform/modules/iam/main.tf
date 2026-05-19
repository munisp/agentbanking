# ─────────────────────────────────────────────────────────────────────────────
# IAM Module — Roles and policies for EKS, RDS, S3, and service accounts
# ─────────────────────────────────────────────────────────────────────────────

variable "project_name" { type = string }
variable "environment" { type = string }
variable "account_id" { type = string }

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ── EKS Cluster Role ──────────────────────────────────────────────────────────

resource "aws_iam_role" "eks_cluster" {
  name = "${local.name_prefix}-eks-cluster-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role_policy_attachment" "eks_vpc_resource_controller" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
}

# ── EKS Node Role ────────────────────────────────────────────────────────────

resource "aws_iam_role" "eks_node" {
  name = "${local.name_prefix}-eks-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_ecr_readonly" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_ssm" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ── Application Service Account Role (IRSA) ──────────────────────────────────

resource "aws_iam_role" "app_service_account" {
  name = "${local.name_prefix}-app-sa-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRoleWithWebIdentity"
      Effect    = "Allow"
      Principal = { Federated = "arn:aws:iam::${var.account_id}:oidc-provider/oidc.eks.us-east-1.amazonaws.com" }
      Condition = {
        StringEquals = {
          "oidc.eks.us-east-1.amazonaws.com:sub" = "system:serviceaccount:pos-54link:app-service-account"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "app_s3_access" {
  name = "${local.name_prefix}-app-s3-access"
  role = aws_iam_role.app_service_account.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${local.name_prefix}-storage",
          "arn:aws:s3:::${local.name_prefix}-storage/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [
          "arn:aws:kms:*:${var.account_id}:key/*"
        ]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.us-east-1.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "app_secrets_access" {
  name = "${local.name_prefix}-app-secrets-access"
  role = aws_iam_role.app_service_account.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = ["arn:aws:secretsmanager:*:${var.account_id}:secret:${local.name_prefix}/*"]
    }]
  })
}

# ── CI/CD Deploy Role ─────────────────────────────────────────────────────────

resource "aws_iam_role" "cicd_deploy" {
  name = "${local.name_prefix}-cicd-deploy-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRoleWithWebIdentity"
      Effect    = "Allow"
      Principal = { Federated = "arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com" }
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:pos-54link/*:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "cicd_eks_access" {
  name = "${local.name_prefix}-cicd-eks-access"
  role = aws_iam_role.cicd_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["eks:DescribeCluster", "eks:ListClusters"]
        Resource = ["arn:aws:eks:*:${var.account_id}:cluster/${local.name_prefix}-*"]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = ["arn:aws:ecr:*:${var.account_id}:repository/${local.name_prefix}-*"]
      }
    ]
  })
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "eks_cluster_role_arn" { value = aws_iam_role.eks_cluster.arn }
output "eks_node_role_arn" { value = aws_iam_role.eks_node.arn }
output "app_sa_role_arn" { value = aws_iam_role.app_service_account.arn }
output "cicd_deploy_role_arn" { value = aws_iam_role.cicd_deploy.arn }
