# Rule Engine Service

## Overview

This service provides a robust and scalable rule engine for the Remittance Platform. It allows for the dynamic definition, evaluation, and execution of business rules, enabling flexible and adaptive decision-making processes. The service is built using FastAPI, SQLAlchemy for ORM, and PostgreSQL as the primary data store.

## Features

- **Dynamic Rule Management**: Create, read, update, and delete rules, conditions, and actions via a RESTful API.
- **Flexible Rule Definition**: Define complex rules with multiple conditions and associated actions.
- **Production-Ready**: Includes comprehensive error handling, structured logging, authentication, and monitoring capabilities.
- **Scalable Architecture**: Designed for high performance and scalability using FastAPI and asynchronous operations.
- **API Documentation**: Automatic OpenAPI (Swagger UI) documentation for all endpoints.
- **Health Checks & Metrics**: Integrated health check endpoint and Prometheus metrics for operational visibility.

## Project Structure

```
rule-engine/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py         # API endpoints for rules management
│   ├── core/
│   │   ├── config.py                # Application configuration settings
│   │   ├── exceptions.py            # Custom exception classes
│   │   ├── health.py                # Health check endpoint
│   │   ├── logging_config.py        # Logging configuration
│   │   ├── metrics.py               # Prometheus metrics implementation
│   │   └── security.py              # Authentication and authorization utilities
│   ├── db/
│   │   └── database.py              # Database connection and session management
│   ├── models/
│   │   └── models.py                # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── schemas.py               # Pydantic schemas for request/response validation
│   ├── services/
│   │   └── rule_service.py          # Business logic for rule operations
│   └── main.py                      # Main FastAPI application entry point
├── docs/                            # Documentation files (e.g., API specs, architectural diagrams)
├── .env.example                     # Example environment variables file
├── requirements.txt                 # Python dependencies
└── README.md                        # Project README and documentation
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- PostgreSQL database
- Docker (optional, for local development setup)

### 1. Clone the repository

```bash
git clone <repository-url>
cd rule-engine
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the root directory of the project based on `.env.example`:

```ini
DATABASE_URL="postgresql://user:password@host:port/dbname"
SECRET_KEY="your-super-secret-key"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional: AWS S3 for future use
# AWS_ACCESS_KEY_ID="your_aws_access_key_id"
# AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key"
# AWS_REGION="your_aws_region"
# S3_BUCKET_NAME="your_s3_bucket_name"

# Optional: Redis for future use
# REDIS_URL="redis://localhost:6379/0"
```

**Note**: Replace placeholder values with your actual database credentials and a strong secret key.

### 4. Run the application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation (Swagger UI) will be available at `http://localhost:8000/api/v1/docs`.

## API Endpoints

The service exposes the following endpoints under the `/api/v1` prefix:

| Method | Endpoint             | Description                                  | Request Body (Schema) | Response Body (Schema) |
| :----- | :------------------- | :------------------------------------------- | :-------------------- | :--------------------- |
| `POST` | `/rules/`            | Create a new rule.                           | `RuleCreate`          | `Rule`                 |
| `GET`  | `/rules/`            | Retrieve a list of all rules.                | None                  | `List[Rule]`           |
| `GET`  | `/rules/{rule_id}`   | Retrieve a specific rule by ID.              | None                  | `Rule`                 |
| `PUT`  | `/rules/{rule_id}`   | Update an existing rule by ID.               | `RuleUpdate`          | `Rule`                 |
| `DELETE`| `/rules/{rule_id}`   | Delete a rule by ID.                         | None                  | `{"ok": True}`         |
| `GET`  | `/health`            | Health check endpoint.                       | None                  | `{"status": "ok"}`   |
| `GET`  | `/metrics`           | Prometheus metrics endpoint.                 | None                  | Prometheus metrics     |

## Authentication and Authorization

(Placeholder for future implementation)

This service is designed to integrate with a JWT-based authentication system. The `app/core/security.py` module provides utilities for password hashing and JWT token creation/decoding. Protected routes would typically use a dependency injection to validate the JWT token and extract user information.

## Error Handling

Custom exceptions are defined in `app/core/exceptions.py` to provide specific error responses for common scenarios (e.g., `RuleNotFoundException`, `RuleAlreadyExistsException`). These exceptions are caught and handled by FastAPI, returning appropriate HTTP status codes and detailed messages.

## Logging

Structured logging is configured via `app/core/logging_config.py` using Python's standard `logging` module. Logs are output to `stdout` and include timestamps, log levels, and module names for easy debugging and monitoring in production environments.

## Health Checks and Metrics

- **Health Check**: The `/health` endpoint provides a simple way to check the service's operational status, including database connectivity.
- **Prometheus Metrics**: The `/metrics` endpoint exposes Prometheus-compatible metrics (e.g., request count, latency, in-progress requests) for monitoring the service's performance and resource utilization.

## Technologies Used

- **FastAPI**: Web framework for building APIs.
- **Pydantic**: Data validation and settings management.
- **SQLAlchemy**: ORM for interacting with PostgreSQL.
- **PostgreSQL**: Relational database.
- **python-jose**: JWT (JSON Web Token) implementation.
- **passlib**: Password hashing utilities.
- **prometheus_client**: Python client for Prometheus metrics.
- **Uvicorn**: ASGI server.

