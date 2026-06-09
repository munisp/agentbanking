# middleware-integration

## Overview

Middleware orchestration layer with service discovery and load balancing

## Features

- Feature 1
- Feature 2
- Feature 3

## API Endpoints

### Health Check
```
GET /health
```

### [Endpoint Group]
```
POST /api/v1/[resource]
GET /api/v1/[resource]/{id}
PUT /api/v1/[resource]/{id}
DELETE /api/v1/[resource]/{id}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql://user:pass@localhost/db |
| REDIS_URL | Redis connection string | redis://localhost:6379 |
| KAFKA_BOOTSTRAP_SERVERS | Kafka brokers | localhost:9092 |

## Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start service
uvicorn main:app --reload
```

### Testing
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

### Docker
```bash
# Build image
docker build -t middleware-integration:latest .

# Run container
docker run -p 8000:8000 middleware-integration:latest
```

## Deployment

See [deployment guide](docs/deployment.md)

## API Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

Proprietary - Remittance Platform V11.0
