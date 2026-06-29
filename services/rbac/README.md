# RBAC Service for Remittance Platform

## Overview

This is a production-ready Role-Based Access Control (RBAC) service built with FastAPI, designed for integration into an Remittance Platform. It provides robust authentication and authorization mechanisms, managing users, roles, and permissions to secure access to various functionalities within the platform.

## Features

- **User Management**: Create, read, update, and delete user accounts.
- **Role Management**: Define and manage roles with specific descriptions.
- **Permission Management**: Define and manage granular permissions.
- **Role-Permission Assignment**: Assign multiple permissions to roles.
- **User-Role Assignment**: Assign multiple roles to users.
- **Authentication**: Secure user login using JWT (JSON Web Tokens).
- **Authorization**: Endpoint-level authorization based on assigned roles and permissions.
- **Database Integration**: Uses PostgreSQL with SQLAlchemy ORM for data persistence.
- **Configuration Management**: Centralized configuration using environment variables.
- **Error Handling**: Comprehensive exception handling for API endpoints.
- **Logging**: Structured logging for better observability and debugging.
- **Health Checks & Metrics**: Basic endpoints for monitoring service health and performance.
- **API Documentation**: Automatic interactive API documentation (Swagger UI/ReDoc).

## Technology Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (via SQLAlchemy)
- **ORM**: SQLAlchemy
- **Authentication**: JWT (JSON Web Tokens)
- **Password Hashing**: `passlib` with `bcrypt`
- **Data Validation**: Pydantic
- **ASGI Server**: Uvicorn

## Project Structure

```
rbac_service/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── permissions.py
│   │   ├── roles.py
│   │   └── users.py
│   ├── config/
│   │   └── config.py
│   ├── crud/
│   │   ├── __init__.py
│   │   ├── crud_permission.py
│   │   ├── crud_role.py
│   │   └── crud_user.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── main.py
├── requirements.txt
└── README.md
```

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL database
- `pip` for package management

### 1. Clone the repository

```bash
git clone <repository_url>
cd rbac_service
```

### 2. Create a virtual environment and activate it

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

Ensure you have a PostgreSQL database running. Create a database for the RBAC service (e.g., `rbac_db`).

### 5. Environment Variables

Create a `.env` file in the `rbac_service/` directory or set the following environment variables:

```env
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rbac_db
SECRET_KEY=your_super_secret_key_for_jwt
# REDIS_HOST=localhost
# REDIS_PORT=6379
# S3_BUCKET_NAME=rbac-s3-bucket
# S3_ACCESS_KEY_ID=your_s3_access_key
# S3_SECRET_ACCESS_KEY=your_s3_secret_key
```

**Note**: `SECRET_KEY` is crucial for JWT token signing. Generate a strong, random key for production.

### 6. Run the Application

Navigate to the `app` directory and run the FastAPI application using Uvicorn:

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be accessible at `http://0.0.0.0:8000`.

## API Documentation

Once the service is running, you can access the interactive API documentation:

- **Swagger UI**: `http://0.0.0.0:8000/api/docs`
- **ReDoc**: `http://0.0.0.0:8000/api/redoc`

## Usage

### Authentication

To get an access token, send a POST request to `/token` with `username` and `password` in the request body (form-data).

Example (using `curl`):

```bash
curl -X POST "http://localhost:8000/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=testuser&password=testpassword"
```

This will return a JWT `access_token` which you should include in the `Authorization` header of subsequent requests as a Bearer token.

### Example Flow: Create User, Role, Permission

1. **Create Permissions** (e.g., `create_user`, `view_users`, `create_role`, `view_roles`, etc.)
2. **Create Roles** and assign permissions to them.
3. **Create Users** and assign roles to them.
4. Access protected endpoints using the generated JWT token for a user with appropriate roles and permissions.

## Health Checks and Metrics

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (placeholder, integrate with Prometheus for real metrics)

## Error Handling

The service implements global exception handlers for:

- `RequestValidationError` (HTTP 422): For invalid request payloads.
- `SQLAlchemyError` (HTTP 500): For database-related issues.
- `HTTPException` (various codes): For explicit HTTP errors raised within endpoints.
- `Exception` (HTTP 500): For any unhandled exceptions.

All errors are logged with relevant details.

## Logging

Logging is configured to output to `stdout` with `INFO` level. This can be customized via the `logging_config` dictionary in `main.py`.

## Security Considerations

- **JWT Secret Key**: Ensure `SECRET_KEY` is a strong, randomly generated string and kept secure in production environments.
- **Password Hashing**: Passwords are hashed using `bcrypt`.
- **HTTPS**: Always deploy the service behind an HTTPS proxy in production.
- **Input Validation**: Pydantic models ensure robust input validation.
- **Authorization**: Granular permission checks are enforced at the endpoint level.

## Future Enhancements

- Integration with a dedicated metrics system (e.g., Prometheus, Grafana).
- More sophisticated logging aggregation (e.g., ELK stack).
- Rate limiting for API endpoints.
- Caching mechanisms (e.g., Redis) for frequently accessed data.
- Comprehensive unit and integration tests.
- Dockerization and Kubernetes deployment configurations.

---

**Manus AI**
October 2025

