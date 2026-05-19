# Background Check Service

Automated background verification service for agent onboarding in the Remittance Platform V11.0.

## Overview

The Background Check Service integrates with third-party providers to perform comprehensive background verification including identity verification, criminal record checks, credit history, employment verification, and reference checks.

## Features

- **Identity Verification** - Verify NIN/BVN using Smile Identity
- **Criminal Record Check** - Check against Nigeria Police Force, EFCC, ICPC databases
- **Credit History** - Credit score and payment history from CRC Credit Bureau
- **Employment Verification** - Verify employment history
- **Reference Checks** - Contact and verify references
- **Address Verification** - Verify residential address
- **Async Processing** - Background tasks with real-time progress tracking
- **Event Publishing** - Kafka events for completed checks
- **Caching** - Redis caching for repeated checks
- **Authorization** - Permify fine-grained access control

## API Endpoints

### Initiate Background Check
```
POST /api/v1/background-check/initiate
```

**Request Body:**
```json
{
  "agent_id": "agent_123",
  "check_types": ["identity", "criminal_record", "credit_history"],
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1990-01-15",
  "phone_number": "+2348012345678",
  "email": "john.doe@example.com",
  "address": "123 Main St, Lagos",
  "nin": "12345678901",
  "bvn": "22222222222"
}
```

**Response:**
```json
{
  "check_id": "uuid-here",
  "agent_id": "agent_123",
  "status": "pending",
  "created_at": "2025-11-11T10:00:00Z",
  "estimated_completion": "2025-11-11T10:15:00Z",
  "message": "Background check initiated with 3 checks"
}
```

### Get Check Status
```
GET /api/v1/background-check/{check_id}/status
```

**Response:**
```json
{
  "check_id": "uuid-here",
  "agent_id": "agent_123",
  "status": "in_progress",
  "progress": 66,
  "checks_completed": 2,
  "checks_total": 3,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:10:00Z"
}
```

### Get Check Results
```
GET /api/v1/background-check/{check_id}/results
```

**Response:**
```json
{
  "check_id": "uuid-here",
  "agent_id": "agent_123",
  "overall_status": "completed",
  "overall_result": "pass",
  "checks": [
    {
      "check_type": "identity",
      "status": "completed",
      "result": "pass",
      "details": {
        "match": true,
        "confidence": 0.95
      },
      "provider": "Smile Identity",
      "checked_at": "2025-11-11T10:05:00Z"
    }
  ],
  "created_at": "2025-11-11T10:00:00Z",
  "completed_at": "2025-11-11T10:15:00Z"
}
```

### Retry Failed Check
```
POST /api/v1/background-check/{check_id}/retry
```

### Delete Check
```
DELETE /api/v1/background-check/{check_id}
```

### Get Agent Checks
```
GET /api/v1/background-check/agent/{agent_id}
```

## Environment Variables

```bash
# Third-party API keys
SMILE_IDENTITY_API_KEY=your_smile_api_key
SMILE_IDENTITY_PARTNER_ID=your_partner_id
YOUVERIFY_API_KEY=your_youverify_key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/background_check

# Keycloak
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=remittance
KEYCLOAK_CLIENT_ID=background-check-service

# Permify
PERMIFY_URL=http://localhost:3478

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:19092,localhost:19093,localhost:19094

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3500
DAPR_GRPC_PORT=50001
```

## Deployment

### Docker
```bash
docker build -t background-check-service .
docker run -p 8100:8100 --env-file .env background-check-service
```

### Docker Compose
```bash
docker-compose up background-check-service
```

### With Dapr Sidecar
```bash
dapr run --app-id background-check-service \
         --app-port 8100 \
         --dapr-http-port 3500 \
         -- python main.py
```

## Testing

Run unit tests:
```bash
pytest tests/
```

Run integration tests:
```bash
pytest tests/integration/
```

## Integration with Temporal Workflow

The background check service is integrated with the Agent Onboarding Workflow:

```python
# In agent onboarding workflow
background_check_result = await workflow.execute_activity(
    initiate_background_check,
    args=[agent_data],
    start_to_close_timeout=timedelta(minutes=30)
)

if background_check_result["overall_result"] != "pass":
    await workflow.execute_activity(
        reject_agent_application,
        args=[agent_id, "Failed background check"]
    )
```

## Monitoring

- **Prometheus Metrics:** http://localhost:8100/metrics
- **Health Check:** http://localhost:8100/health
- **Logs:** Structured JSON logging to stdout

## Security

- **Authentication:** Keycloak JWT tokens required for all endpoints
- **Authorization:** Permify fine-grained permissions
- **Data Encryption:** All sensitive data encrypted at rest and in transit
- **Audit Trail:** All checks logged for compliance

## Support

For issues or questions, contact the platform team.

**Version:** 1.0.0  
**Last Updated:** November 11, 2025

