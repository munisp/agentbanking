# ─────────────────────────────────────────────────────────────────────────────
# POS-54Link — Staging Environment Variables
# ─────────────────────────────────────────────────────────────────────────────

aws_region   = "us-east-1"
project_name = "pos-54link"
environment  = "staging"

# VPC
vpc_cidr = "10.2.0.0/16"

# EKS
eks_cluster_version     = "1.29"
eks_node_instance_types = ["m6i.large", "m6a.large"]
eks_node_desired_size   = 3
eks_node_min_size       = 2
eks_node_max_size       = 6
eks_node_disk_size      = 80

# RDS PostgreSQL
rds_instance_class        = "db.r6g.large"
rds_allocated_storage     = 50
rds_max_allocated_storage = 200
rds_engine_version        = "16.2"
rds_database_name         = "pos54link_staging"
rds_master_username       = "pos_admin"

# ElastiCache Redis
redis_node_type       = "cache.r6g.medium"
redis_num_cache_nodes = 2
redis_engine_version  = "7.1"

# Monitoring
alert_email = "staging@pos-54link.com"
