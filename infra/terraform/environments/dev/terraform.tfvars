# ─────────────────────────────────────────────────────────────────────────────
# POS-54Link — Development Environment Variables
# ─────────────────────────────────────────────────────────────────────────────

aws_region   = "us-east-1"
project_name = "pos-54link"
environment  = "dev"

# VPC
vpc_cidr = "10.1.0.0/16"

# EKS
eks_cluster_version     = "1.29"
eks_node_instance_types = ["t3.large"]
eks_node_desired_size   = 2
eks_node_min_size       = 1
eks_node_max_size       = 4
eks_node_disk_size      = 50

# RDS PostgreSQL
rds_instance_class        = "db.t4g.medium"
rds_allocated_storage     = 20
rds_max_allocated_storage = 100
rds_engine_version        = "16.2"
rds_database_name         = "pos54link_dev"
rds_master_username       = "pos_admin"

# ElastiCache Redis
redis_node_type       = "cache.t4g.medium"
redis_num_cache_nodes = 1
redis_engine_version  = "7.1"

# Monitoring
alert_email = "dev@pos-54link.com"
