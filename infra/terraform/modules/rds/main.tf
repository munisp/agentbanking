# ─────────────────────────────────────────────────────────────────────────────
# RDS Module — PostgreSQL with Multi-AZ, encryption, automated backups
# ─────────────────────────────────────────────────────────────────────────────

variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "instance_class" { type = string }
variable "allocated_storage" { type = number }
variable "max_allocated_storage" { type = number }
variable "engine_version" { type = string }
variable "database_name" { type = string }
variable "master_username" { type = string }
variable "multi_az" {
  type    = bool
  default = true
}
variable "backup_retention" {
  type    = number
  default = 30
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "eks_security_group_id" { type = string }

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ── Subnet Group ──────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${local.name_prefix}-db-subnet-group" }
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "rds" {
  name_prefix = "${local.name_prefix}-rds-"
  vpc_id      = var.vpc_id
  description = "RDS PostgreSQL security group for ${local.name_prefix}"

  tags = { Name = "${local.name_prefix}-rds-sg" }
}

resource "aws_security_group_rule" "rds_ingress_postgres" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.rds.id
  description              = "PostgreSQL access from EKS cluster"
}

resource "aws_security_group_rule" "rds_egress_https" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.rds.id
  description       = "Allow HTTPS outbound for AWS APIs and updates"
}

# ── Parameter Group ───────────────────────────────────────────────────────────

resource "aws_db_parameter_group" "main" {
  name   = "${local.name_prefix}-pg16-params"
  family = "postgres16"

  parameter {
    name         = "shared_buffers"
    value        = "{DBInstanceClassMemory/4}"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "effective_cache_size"
    value        = "{DBInstanceClassMemory*3/4}"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "work_mem"
    value        = "65536"
    apply_method = "immediate"
  }
  parameter {
    name         = "maintenance_work_mem"
    value        = "524288"
    apply_method = "immediate"
  }
  parameter {
    name         = "random_page_cost"
    value        = "1.1"
    apply_method = "immediate"
  }
  parameter {
    name         = "effective_io_concurrency"
    value        = "200"
    apply_method = "immediate"
  }
  parameter {
    name         = "max_parallel_workers_per_gather"
    value        = "4"
    apply_method = "immediate"
  }
  parameter {
    name         = "max_parallel_workers"
    value        = "8"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "wal_buffers"
    value        = "65536"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "checkpoint_completion_target"
    value        = "0.9"
    apply_method = "immediate"
  }
  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
    apply_method = "immediate"
  }
  parameter {
    name         = "log_checkpoints"
    value        = "1"
    apply_method = "immediate"
  }
  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "immediate"
  }
  parameter {
    name         = "log_disconnections"
    value        = "1"
    apply_method = "immediate"
  }
  parameter {
    name         = "log_lock_waits"
    value        = "1"
    apply_method = "immediate"
  }
  parameter {
    name         = "idle_in_transaction_session_timeout"
    value        = "60000"
    apply_method = "immediate"
  }
  parameter {
    name         = "statement_timeout"
    value        = "30000"
    apply_method = "immediate"
  }
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  tags = { Name = "${local.name_prefix}-pg-params" }
}

# ── KMS Key ───────────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "rds" {
  description             = "RDS encryption key for ${local.name_prefix}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "rds-key-policy"
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

  tags = { Name = "${local.name_prefix}-rds-kms" }
}

# ── RDS Instance ──────────────────────────────────────────────────────────────

resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name                     = var.database_name
  username                    = var.master_username
  manage_master_user_password = true

  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = var.backup_retention
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  copy_tags_to_snapshot   = true

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = var.environment == "production" ? "${local.name_prefix}-final-snapshot" : null

  iam_database_authentication_enabled = true
  auto_minor_version_upgrade          = true

  performance_insights_enabled          = true
  performance_insights_retention_period = var.environment == "production" ? 731 : 7
  performance_insights_kms_key_id       = aws_kms_key.rds.arn
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = { Name = "${local.name_prefix}-postgres" }
}

# ── Read Replica (Production Only) ────────────────────────────────────────────

resource "aws_db_instance" "read_replica" {
  count               = var.environment == "production" ? 1 : 0
  identifier          = "${local.name_prefix}-postgres-replica"
  replicate_source_db = aws_db_instance.main.identifier
  instance_class      = var.instance_class
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.rds.arn

  multi_az                            = true
  deletion_protection                 = true
  auto_minor_version_upgrade          = true
  performance_insights_enabled        = true
  performance_insights_kms_key_id     = aws_kms_key.rds.arn
  monitoring_interval                 = 60
  monitoring_role_arn                 = aws_iam_role.rds_monitoring.arn
  copy_tags_to_snapshot               = true
  iam_database_authentication_enabled = true
  enabled_cloudwatch_logs_exports     = ["postgresql", "upgrade"]

  tags = { Name = "${local.name_prefix}-postgres-replica" }
}

# ── Enhanced Monitoring Role ──────────────────────────────────────────────────

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "endpoint" { value = aws_db_instance.main.endpoint }
output "database_name" { value = aws_db_instance.main.db_name }
output "instance_id" { value = aws_db_instance.main.id }
output "port" { value = aws_db_instance.main.port }
