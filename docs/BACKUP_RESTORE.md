# 54Link Backup & Restore Procedures

## Overview

This document covers backup and restore procedures for all 54Link data stores.

---

## 1. PostgreSQL Database

### Automated Backups

#### Daily Full Backup (via cron)

```bash
# /etc/cron.d/54link-db-backup
0 2 * * * postgres pg_dump -Fc -Z6 \
  --dbname=$DATABASE_URL \
  --file=/backups/postgres/54link-$(date +\%Y\%m\%d-\%H\%M).dump \
  && find /backups/postgres -name "*.dump" -mtime +30 -delete
```

#### Continuous WAL Archiving (Point-in-Time Recovery)

```ini
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://54link-backups/wal/%f --sse AES256'
```

### Manual Backup

```bash
# Full database dump (compressed custom format)
pg_dump -Fc -Z6 \
  --dbname="postgresql://postgres:${DB_PASSWORD}@localhost:5432/ngapp" \
  --file=/backups/54link-$(date +%Y%m%d-%H%M).dump

# Schema only (for migration reference)
pg_dump --schema-only \
  --dbname="postgresql://postgres:${DB_PASSWORD}@localhost:5432/ngapp" \
  > /backups/54link-schema-$(date +%Y%m%d).sql

# Verify backup integrity
pg_restore --list /backups/54link-$(date +%Y%m%d-%H%M).dump | head
```

### Restore

#### Full Restore

```bash
# Stop all services first
docker compose -f docker-compose.production.yml stop api

# Drop and recreate database
psql -U postgres -c "DROP DATABASE IF EXISTS ngapp;"
psql -U postgres -c "CREATE DATABASE ngapp;"

# Restore from backup
pg_restore -d ngapp -U postgres --clean --if-exists \
  /backups/54link-YYYYMMDD-HHMM.dump

# Verify
psql -U postgres -d ngapp -c "SELECT count(*) FROM agents;"

# Restart services
docker compose -f docker-compose.production.yml start api
```

#### Point-in-Time Recovery

```bash
# 1. Stop PostgreSQL
systemctl stop postgresql

# 2. Clear data directory
rm -rf /var/lib/postgresql/data/*

# 3. Restore base backup
aws s3 cp s3://54link-backups/base/latest.tar.gz /tmp/
tar xzf /tmp/latest.tar.gz -C /var/lib/postgresql/data/

# 4. Create recovery.conf
cat > /var/lib/postgresql/data/recovery.conf << EOF
restore_command = 'aws s3 cp s3://54link-backups/wal/%f %p'
recovery_target_time = '2025-01-15 14:30:00 WAT'
recovery_target_action = 'promote'
EOF

# 5. Start PostgreSQL
systemctl start postgresql
```

---

## 2. Redis

### Backup

```bash
# Trigger RDB snapshot
redis-cli BGSAVE

# Wait for completion
redis-cli LASTSAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb /backups/redis/dump-$(date +%Y%m%d-%H%M).rdb
```

### Restore

```bash
# Stop Redis
systemctl stop redis

# Replace RDB file
cp /backups/redis/dump-YYYYMMDD-HHMM.rdb /var/lib/redis/dump.rdb
chown redis:redis /var/lib/redis/dump.rdb

# Start Redis
systemctl start redis

# Verify
redis-cli INFO keyspace
```

---

## 3. Kafka Topics

### Backup (Topic Configs + Offsets)

```bash
# Export topic configurations
kafka-topics.sh --bootstrap-server localhost:9092 --describe \
  > /backups/kafka/topics-$(date +%Y%m%d).txt

# Export consumer group offsets
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --all-groups --describe \
  > /backups/kafka/offsets-$(date +%Y%m%d).txt
```

### Note

Kafka messages are transient by design. For long-term message retention, use the Lakehouse service (Fluvio → MinIO/S3).

---

## 4. Keycloak

### Backup

```bash
# Export realm configuration
docker exec keycloak /opt/keycloak/bin/kc.sh export \
  --realm 54link \
  --dir /tmp/keycloak-export

# Copy from container
docker cp keycloak:/tmp/keycloak-export /backups/keycloak/$(date +%Y%m%d)/
```

### Restore

```bash
# Import realm configuration
docker exec keycloak /opt/keycloak/bin/kc.sh import \
  --dir /tmp/keycloak-export \
  --override true
```

---

## 5. Application Files & Config

### Backup

```bash
# Application configuration
tar czf /backups/config/54link-config-$(date +%Y%m%d).tar.gz \
  .env \
  docker-compose.production.yml \
  helm/54link/values.yaml \
  monitoring/ \
  terraform/

# Upload to S3
aws s3 sync /backups/ s3://54link-backups/ --sse AES256
```

---

## Backup Schedule

| Data Store        | Frequency       | Retention | Storage |
| ----------------- | --------------- | --------- | ------- |
| PostgreSQL (full) | Daily 02:00 WAT | 30 days   | S3      |
| PostgreSQL (WAL)  | Continuous      | 7 days    | S3      |
| Redis (RDB)       | Every 6 hours   | 7 days    | S3      |
| Keycloak realm    | Weekly          | 90 days   | S3      |
| App config        | On every deploy | 90 days   | S3      |

## Backup Verification

Run weekly restore test on staging:

```bash
# Automated restore test (runs every Sunday 04:00 WAT)
# Restores latest backup to staging and runs health checks
./scripts/verify-backup.sh --target staging --latest
```

---

## Disaster Recovery

### RTO / RPO Targets

| Scenario                 | RPO                     | RTO                  |
| ------------------------ | ----------------------- | -------------------- |
| Database corruption      | 5 min (WAL)             | 30 min               |
| Full infrastructure loss | 24 hours (daily backup) | 4 hours              |
| Single service failure   | 0 (no data loss)        | 5 min (auto-restart) |

### DR Steps

1. Provision new infrastructure (Terraform): `terraform apply -auto-approve`
2. Restore database from S3 backup
3. Restore Keycloak realm config
4. Deploy application via Helm
5. Verify health checks
6. Update DNS records
