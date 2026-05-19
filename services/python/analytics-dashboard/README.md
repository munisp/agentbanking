
# Analytics Dashboard Service

This service provides a robust and scalable backend for the Remittance Platform's analytics dashboard. It is built using FastAPI, SQLAlchemy, and PostgreSQL, designed for production readiness with comprehensive features including data management, authentication, authorization, logging, and health checks.

## Features

-   **User Activity Tracking**: Record and retrieve user interactions within the platform.
-   **Transaction Monitoring**: Manage and query financial transactions.
-   **Metric Collection**: Store and retrieve key performance indicators and operational metrics.
-   **Alert Management**: Define and track alerts based on metric thresholds.
-   **Authentication (JWT)**: Secure API access using JSON Web Tokens.
-   **Authorization (API Key with Scopes)**: Granular control over API access based on predefined scopes.
-   **Configuration Management**: Externalized settings using Pydantic BaseSettings.
-   **Logging**: Structured logging for better observability and debugging.
-   **Health Checks**: Endpoint to monitor service and database health.
-   **Automatic API Documentation**: OpenAPI (Swagger UI/ReDoc) documentation generated automatically by FastAPI.

## Technologies Used

-   **FastAPI**: High-performance web framework for building APIs.
-   **SQLAlchemy**: SQL toolkit and Object-Relational Mapper (ORM) for database interaction.
-   **PostgreSQL**: Relational database for data storage.
-   **Pydantic**: Data validation and settings management using Python type hints.
-   **python-jose**: For JWT token handling.
-   **passlib**: For password hashing.

## Setup and Installation

### Prerequisites

-   Python 3.9+
-   Poetry (recommended for dependency management) or pip
-   PostgreSQL database instance

### 1. Clone the repository

```bash
git clone <repository-url>
cd analytics-dashboard
```

### 2. Create a virtual environment and install dependencies

Using Poetry:

```bash
poetry install
poetry shell
```

Using pip:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Database Configuration

Ensure your PostgreSQL database is running. Update the `DATABASE_URL` in `.env` file (create one if it doesn't exist) with your database connection string.

Example `.env` file:

```
SECRET_KEY="your-super-secret-jwt-key"
DATABASE_URL="postgresql://user:password@host:port/dbname"
API_KEYS='{"analytics-key": ["read", "write"], "another-key": ["read"]}'
```

### 4. Run Database Migrations (Initial Setup)

This service uses SQLAlchemy's `create_all` for initial table creation. For production, consider using a dedicated migration tool like Alembic.

```python
# From a Python interpreter or a script:
from database import engine, Base
Base.metadata.create_all(bind=engine)
```

### 5. Run the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation will be available at `http://0.0.0.0:8000/docs` (Swagger UI) and `http://0.0.0.0:8000/redoc` (ReDoc).

## API Endpoints

The service exposes the following main endpoint categories:

-   `/health`: Service health check.
-   `/token`: Obtain JWT access token.
-   `/user-activities/`: CRUD operations for user activities.
-   `/transactions/`: CRUD operations for financial transactions.
-   `/metrics/`: CRUD operations for performance metrics.
-   `/alerts/`: CRUD operations for system alerts.

Detailed API documentation, including request/response schemas and authentication methods, is available via the automatically generated OpenAPI documentation at `/docs` and `/redoc`.

## Authentication and Authorization

This service supports two forms of authentication:

1.  **JWT Bearer Token**: For user-based authentication. Obtain a token from the `/token` endpoint using a username and password (currently a mock user `testuser`/`testpassword`). This token should be sent in the `Authorization` header as `Bearer <token>`.
2.  **API Key**: For service-to-service authentication or specific integrations. API keys are defined in the `.env` file and sent via the `X-API-Key` header. API keys can be assigned specific scopes (e.g., `read`, `write`) to control access to different endpoints.

## Logging

Logging is configured to output to `stderr` with `INFO` level by default. You can adjust the logging configuration in `main.py` or via environment variables if using a more advanced logging setup.

## Error Handling

Comprehensive error handling is implemented using FastAPI's `HTTPException` to return appropriate HTTP status codes and detailed error messages for common scenarios like resource not found, unauthorized access, and validation errors.

## Health Checks and Metrics

-   A `/health` endpoint is available to check the service's operational status and database connectivity.
-   Metrics are stored in the database and can be retrieved via the `/metrics` endpoint. For production monitoring, integrate with external monitoring systems (e.g., Prometheus, Grafana) to scrape these metrics.

## Contributing

Contributions are welcome! Please follow standard development practices:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes and write tests.
4.  Ensure all tests pass.
5.  Submit a pull request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

