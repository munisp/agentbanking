# ─────────────────────────────────────────────────────────────────────────────
# POS-54Link — Production Environment Variables
# ─────────────────────────────────────────────────────────────────────────────

aws_region   = "us-east-1"
project_name = "pos-54link"
environment  = "production"

# VPC
vpc_cidr = "10.0.0.0/16"

# EKS
eks_cluster_version     = "1.29"
eks_node_instance_types = ["m6i.xlarge", "m6a.xlarge"]
eks_node_desired_size   = 4
eks_node_min_size       = 3
eks_node_max_size       = 15
eks_node_disk_size      = 100

# RDS PostgreSQL
rds_instance_class        = "db.r6g.xlarge"
rds_allocated_storage     = 200
rds_max_allocated_storage = 1000
rds_engine_version        = "16.2"
rds_database_name         = "pos54link"
rds_master_username       = "pos_admin"

# ElastiCache Redis
redis_node_type       = "cache.r6g.large"
redis_num_cache_nodes = 3
redis_engine_version  = "7.1"

# Monitoring
alert_email = "ops@pos-54link.com"
