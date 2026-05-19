# ─────────────────────────────────────────────────────────────────────────────
# S3 Module — Encrypted buckets for uploads, backups, and data lake
# ─────────────────────────────────────────────────────────────────────────────

variable "project_name" { type = string }
variable "environment" { type = string }
variable "enable_versioning" {
  type    = bool
  default = true
}
variable "enable_lifecycle" {
  type    = bool
  default = true
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}

# ── KMS Key for S3 Encryption ────────────────────────────────────────────────

resource "aws_kms_key" "s3" {
  description             = "S3 bucket encryption key for ${local.name_prefix}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "s3-key-policy"
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

  tags = { Name = "${local.name_prefix}-s3-kms" }
}

# ── Access Logging Bucket ───────────────────────────────────────────────────

resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.name_prefix}-access-logs"
  tags   = { Name = "${local.name_prefix}-access-logs" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-logs"
    status = "Enabled"
    expiration { days = 365 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_versioning" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_notification" "access_logs" {
  bucket      = aws_s3_bucket.access_logs.id
  eventbridge = true
}

# ── Replication IAM Role ──────────────────────────────────────────────────────

variable "replication_region" {
  type    = string
  default = "us-west-2"
}

resource "aws_iam_role" "replication" {
  name = "${local.name_prefix}-s3-replication-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "replication" {
  name = "${local.name_prefix}-s3-replication-policy"
  role = aws_iam_role.replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.main.arn,
          aws_s3_bucket.backups.arn,
          aws_s3_bucket.datalake.arn,
          aws_s3_bucket.access_logs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Resource = [
          "${aws_s3_bucket.main.arn}/*",
          "${aws_s3_bucket.backups.arn}/*",
          "${aws_s3_bucket.datalake.arn}/*",
          "${aws_s3_bucket.access_logs.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = [
          "arn:aws:s3:::${local.name_prefix}-storage-replica/*",
          "arn:aws:s3:::${local.name_prefix}-backups-replica/*",
          "arn:aws:s3:::${local.name_prefix}-datalake-replica/*",
          "arn:aws:s3:::${local.name_prefix}-access-logs-replica/*"
        ]
      }
    ]
  })
}

# ── Replication Configurations ────────────────────────────────────────────────

resource "aws_s3_bucket_replication_configuration" "main" {
  depends_on = [aws_s3_bucket_versioning.main]
  bucket     = aws_s3_bucket.main.id
  role       = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"
    destination {
      bucket        = "arn:aws:s3:::${local.name_prefix}-storage-replica"
      storage_class = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "backups" {
  depends_on = [aws_s3_bucket_versioning.backups]
  bucket     = aws_s3_bucket.backups.id
  role       = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"
    destination {
      bucket        = "arn:aws:s3:::${local.name_prefix}-backups-replica"
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "datalake" {
  depends_on = [aws_s3_bucket_versioning.datalake]
  bucket     = aws_s3_bucket.datalake.id
  role       = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"
    destination {
      bucket        = "arn:aws:s3:::${local.name_prefix}-datalake-replica"
      storage_class = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "access_logs" {
  depends_on = [aws_s3_bucket_versioning.access_logs]
  bucket     = aws_s3_bucket.access_logs.id
  role       = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"
    destination {
      bucket        = "arn:aws:s3:::${local.name_prefix}-access-logs-replica"
      storage_class = "STANDARD_IA"
    }
  }
}

# ── Primary Application Bucket ────────────────────────────────────────────────

resource "aws_s3_bucket" "main" {
  bucket = "${local.name_prefix}-storage"
  tags   = { Name = "${local.name_prefix}-storage" }
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket                  = aws_s3_bucket.main.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "main" {
  bucket        = aws_s3_bucket.main.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "s3-access-logs/main/"
}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  count  = var.enable_lifecycle ? 1 : 0
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }

  rule {
    id     = "cleanup-multipart"
    status = "Enabled"
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_notification" "main" {
  bucket      = aws_s3_bucket.main.id
  eventbridge = true
}

# ── Backup Bucket ─────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "backups" {
  bucket = "${local.name_prefix}-backups"
  tags   = { Name = "${local.name_prefix}-backups" }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "backups" {
  bucket        = aws_s3_bucket.backups.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "s3-access-logs/backups/"
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "archive-backups"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
    expiration { days = 730 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_notification" "backups" {
  bucket      = aws_s3_bucket.backups.id
  eventbridge = true
}

# ── Data Lake Bucket ──────────────────────────────────────────────────────────

resource "aws_s3_bucket" "datalake" {
  bucket = "${local.name_prefix}-datalake"
  tags   = { Name = "${local.name_prefix}-datalake" }
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket                  = aws_s3_bucket.datalake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "datalake" {
  bucket        = aws_s3_bucket.datalake.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "s3-access-logs/datalake/"
}

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    id     = "datalake-lifecycle"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_notification" "datalake" {
  bucket      = aws_s3_bucket.datalake.id
  eventbridge = true
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "bucket_name" { value = aws_s3_bucket.main.id }
output "bucket_arn" { value = aws_s3_bucket.main.arn }
output "backup_bucket" { value = aws_s3_bucket.backups.id }
output "datalake_bucket" { value = aws_s3_bucket.datalake.id }
