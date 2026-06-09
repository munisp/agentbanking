# PostgreSQL Production Service

Complete production-ready PostgreSQL implementation for the Nigerian Remittance Platform with CDC integration to TigerBeetle.

## Features

✅ **Complete Database Schema**
- User management with KYC tracking
- PIX key resolution
- Transfer metadata (amounts in TigerBeetle)
- Compliance and AML records
- Comprehensive audit logging
- CDC event tracking

✅ **Production API**
- RESTful endpoints
- JWT authentication
- Input validation
- Error handling
- CORS support

✅ **CDC Integration**
- Real-time sync from TigerBeetle
- Async event processing
- Automatic retry on failure
- Event deduplication

✅ **Database Management**
- Alembic migrations
- Connection pooling
- Transaction management
- Health checks

✅ **Security**
- SSL/TLS support
- Encrypted backups
- JWT token authentication
- SQL injection protection

✅ **Operations**
- Automated backups with encryption
- S3 backup upload
- Restore procedures
- Prometheus metrics
- Docker deployment

## Architecture

```
┌─────────────────┐
│   TigerBeetle   │  (Financial data - accounts, transfers, balances)
└────────┬────────┘
         │ CDC Events
         ▼
┌─────────────────┐
│   PostgreSQL    │  (Metadata - users, PIX keys, compliance)
│   Production    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   REST API      │  (Flask application)
└─────────────────┘
```

## Database Schema

### Tables

1. **users** - User profiles and KYC status
2. **pix_keys** - PIX key to TigerBeetle account mapping
3. **transfer_metadata** - Transfer metadata (NO amounts)
4. **audit_logs** - Comprehensive audit trail
5. **compliance_records** - AML/KYC compliance checks
6. **cdc_events** - Change data capture from TigerBeetle

### Key Principles

- **Financial data stays in TigerBeetle** (accounts, balances, transfers)
- **Metadata stays in PostgreSQL** (user profiles, PIX keys, compliance)
- **CDC keeps them in sync** (real-time event processing)

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Local Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=remittance
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

# 3. Run migrations
cd migrations
alembic upgrade head

# 4. Start API
python src/api.py
```

### Docker Setup

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## API Endpoints

### Health Check
```bash
GET /health
```

### User Management
```bash
# Create user
POST /api/v1/users
{
  "email": "user@example.com",
  "phone": "+2348012345678",
  "full_name": "John Doe",
  "country_code": "NGA",
  "tigerbeetle_account_id": 1000001
}

# Get user
GET /api/v1/users/{user_id}
Headers: Authorization: Bearer <token>

# Update KYC status
PUT /api/v1/users/{user_id}/kyc
Headers: Authorization: Bearer <token>
{
  "status": "verified",
  "kyc_data": {...}
}
```

### PIX Key Management
```bash
# Create PIX key
POST /api/v1/pix-keys
Headers: Authorization: Bearer <token>
{
  "pix_key": "user@example.com",
  "user_id": "uuid",
  "tigerbeetle_account_id": 1000001,
  "key_type": "email"
}

# Resolve PIX key
GET /api/v1/pix-keys/{pix_key}

# Get user PIX keys
GET /api/v1/users/{user_id}/pix-keys
Headers: Authorization: Bearer <token>
```

### Transfer Metadata
```bash
# Create transfer metadata
POST /api/v1/transfers
Headers: Authorization: Bearer <token>
{
  "tigerbeetle_transfer_id": 2000001,
  "user_id": "uuid",
  "from_pix_key": "sender@example.com",
  "to_pix_key": "recipient@example.com",
  "currency_code": "NGN",
  "corridor": "PAPSS"
}

# Get user transfers
GET /api/v1/users/{user_id}/transfers?limit=50
Headers: Authorization: Bearer <token>
```

## Database Migrations

```bash
# Create new migration
cd migrations
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Show current version
alembic current
```

## Backup & Restore

### Automated Backup

```bash
# Run backup
./scripts/backup.sh

# With S3 upload
export S3_BUCKET=my-backup-bucket
export BACKUP_ENCRYPTION_KEY=my-secret-key
./scripts/backup.sh
```

### Restore

```bash
# List backups
ls -lh /var/backups/postgresql/

# Restore from backup
./scripts/restore.sh /var/backups/postgresql/remittance_20231024_120000.sql.gz.enc

# Force restore (skip confirmation)
./scripts/restore.sh /path/to/backup.sql.gz --force
```

## Monitoring

### Prometheus Metrics

```bash
# Start metrics exporter
python monitoring/prometheus.py

# View metrics
curl http://localhost:9090/metrics
```

### Available Metrics

- `postgres_connections_active` - Active database connections
- `postgres_connections_idle` - Idle database connections
- `postgres_database_size_bytes` - Database size
- `postgres_users_total` - Total users
- `postgres_users_verified` - KYC verified users
- `postgres_pix_keys_total` - Total PIX keys
- `postgres_transfers_total` - Total transfers
- `postgres_cdc_events_pending` - Pending CDC events

## CDC Integration

### How It Works

1. TigerBeetle creates account/transfer
2. TigerBeetle sends CDC event to PostgreSQL API
3. CDC service processes event asynchronously
4. PostgreSQL metadata updated

### CDC Event Types

- `ACCOUNT_CREATED` - New TigerBeetle account
- `TRANSFER_COMPLETED` - Transfer finalized
- `ACCOUNT_BALANCE_UPDATED` - Balance changed (logged only)

### Starting CDC Service

```bash
# Standalone
python cdc/tigerbeetle_cdc.py

# Docker
docker-compose up cdc-service
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_database.py -v
```

## Production Deployment

### Environment Variables

```bash
# Database
POSTGRES_HOST=your-db-host
POSTGRES_PORT=5432
POSTGRES_DB=remittance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
POSTGRES_SSL_MODE=require
POSTGRES_SSL_ROOT_CERT=/path/to/ca.crt

# Connection Pool
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Backup
BACKUP_DIR=/var/backups/postgresql
RETENTION_DAYS=30
S3_BUCKET=my-backup-bucket
BACKUP_ENCRYPTION_KEY=your-encryption-key

# Monitoring
METRICS_PORT=9090
```

### Security Checklist

- [ ] Use strong PostgreSQL password
- [ ] Enable SSL/TLS for database connections
- [ ] Change JWT secret key
- [ ] Enable backup encryption
- [ ] Restrict database network access
- [ ] Use environment variables for secrets
- [ ] Enable audit logging
- [ ] Configure firewall rules
- [ ] Set up automated backups
- [ ] Monitor metrics and alerts

## Performance Tuning

### PostgreSQL Configuration

See `docker-compose.yml` for optimized PostgreSQL settings:
- `max_connections=200`
- `shared_buffers=256MB`
- `effective_cache_size=1GB`
- Connection pooling enabled

### API Performance

- Connection pooling (10 connections, 20 overflow)
- Pre-ping for connection validation
- Indexed queries on all foreign keys
- Batch operations for CDC events

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
psql -h localhost -p 5432 -U postgres -d remittance

# Check active connections
SELECT count(*) FROM pg_stat_activity;
```

### API Not Starting

```bash
# Check logs
docker-compose logs postgres-api

# Verify database health
curl http://localhost:5433/health
```

### CDC Events Not Processing

```bash
# Check CDC service logs
docker-compose logs cdc-service

# Check pending events
SELECT count(*) FROM cdc_events WHERE processed = false;
```

## License

Proprietary - Nigerian Remittance Platform

## Support

For issues or questions, contact the platform team.

