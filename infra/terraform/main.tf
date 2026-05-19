# ─────────────────────────────────────────────────────────────────────────────
# POS-54Link Platform — Root Terraform Configuration
# Provisions: VPC, EKS, RDS (PostgreSQL), ElastiCache (Redis), S3, IAM, Monitoring
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }

  backend "s3" {
    bucket         = "pos-54link-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "pos-54link-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "pos-54link"
      Environment = var.environment
      ManagedBy   = "terraform"
      Team        = "platform-engineering"
    }
  }
}

# ── Data Sources ──────────────────────────────────────────────────────────────

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ── Modules ───────────────────────────────────────────────────────────────────

module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 3)
  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
}

module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
}

module "eks" {
  source = "./modules/eks"

  project_name        = var.project_name
  environment         = var.environment
  cluster_version     = var.eks_cluster_version
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size
  node_disk_size      = var.eks_node_disk_size
  cluster_role_arn    = module.iam.eks_cluster_role_arn
  node_role_arn       = module.iam.eks_node_role_arn
}

module "rds" {
  source = "./modules/rds"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  instance_class        = var.rds_instance_class
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage
  engine_version        = var.rds_engine_version
  database_name         = var.rds_database_name
  master_username       = var.rds_master_username
  multi_az              = var.environment == "production"
  backup_retention      = var.environment == "production" ? 30 : 7
  deletion_protection   = var.environment == "production"
  eks_security_group_id = module.eks.cluster_security_group_id
}

module "elasticache" {
  source = "./modules/elasticache"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  node_type             = var.redis_node_type
  num_cache_nodes       = var.redis_num_cache_nodes
  engine_version        = var.redis_engine_version
  eks_security_group_id = module.eks.cluster_security_group_id
}

module "s3" {
  source = "./modules/s3"

  project_name      = var.project_name
  environment       = var.environment
  enable_versioning = true
  enable_lifecycle  = true
}

module "monitoring" {
  source = "./modules/monitoring"

  project_name           = var.project_name
  environment            = var.environment
  eks_cluster_name       = module.eks.cluster_name
  rds_instance_id        = module.rds.instance_id
  elasticache_cluster_id = module.elasticache.cluster_id
  sns_alert_email        = var.alert_email
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  value     = module.eks.cluster_endpoint
  sensitive = true
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "rds_database_name" {
  value = module.rds.database_name
}

output "redis_endpoint" {
  value     = module.elasticache.primary_endpoint
  sensitive = true
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}

output "s3_bucket_arn" {
  value = module.s3.bucket_arn
}
