# Data Warehouse Service for Remittance Platform

This service provides a robust and scalable data warehouse solution for the Remittance Platform, built with FastAPI. It offers a set of APIs to manage dimensional data (Agents, Customers, Locations) and fact data (Transactions), along with authentication, authorization, logging, and health monitoring capabilities.

## Features

-   **FastAPI Framework**: High-performance, easy-to-use web framework for building APIs.
-   **SQLAlchemy ORM**: For interacting with PostgreSQL database, defining models, and managing sessions.
-   **Pydantic**: Data validation and serialization for API requests and responses.
-   **JWT Authentication**: Secure token-based authentication for API access.
-   **Comprehensive Logging**: Structured logging for better observability and debugging.
-   **Health Checks**: Endpoints to monitor the health of the service and its dependencies (PostgreSQL, Redis, S3).
-   **Configuration Management**: Environment-variable-based configuration using `pydantic-settings`.
-   **Docker Support**: (Planned) Containerization for easy deployment.

## Project Structure

```
data_warehouse_service/
├── main.py             # Main FastAPI application, endpoints, business logic, security
├── models.py           # SQLAlchemy ORM models and Pydantic schemas
├── config.py           # Application settings and configuration
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

## Setup and Installation

### Prerequisites

-   Python 3.9+
-   Poetry (recommended for dependency management) or pip
-   PostgreSQL database
-   Redis instance
-   AWS S3 bucket (or compatible object storage)

### 1. Clone the repository

```bash
git clone <repository_url>
cd data_warehouse_service
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

### 3. Environment Variables

Create a `.env` file in the root directory of the project and configure the following environment variables:

```dotenv
APP_NAME="DataWarehouseService"
DATABASE_URL="postgresql://user:password@host:port/dbname" # e.g., postgresql://dw_user:dw_password@localhost:5432/dw_db
REDIS_HOST="localhost"
REDIS_PORT=6379
S3_BUCKET_NAME="your-s3-bucket-name"
AWS_ACCESS_KEY_ID="your_aws_access_key_id"
AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key"
LOG_LEVEL="INFO"
SECRET_KEY="a_very_secret_key_for_jwt_signing_replace_me"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Important**: Replace placeholder values with your actual database credentials, Redis connection details, S3 configuration, and a strong `SECRET_KEY`.

## Running the Service

### 1. Initialize the database

The service will automatically create tables based on the SQLAlchemy models when it starts up. Ensure your `DATABASE_URL` is correctly configured and the PostgreSQL database is accessible.

### 2. Start the FastAPI application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

For production, remove `--reload` and consider using a process manager like Gunicorn.

## API Documentation

Once the service is running, you can access the interactive API documentation (Swagger UI) at:

`http://localhost:8000/docs`

Or the ReDoc documentation at:

`http://localhost:8000/redoc`

## API Endpoints

### Authentication

-   `POST /token`: Obtain an access token using username and password.

### Agent Dimension

-   `POST /agents/`: Create a new agent.
-   `GET /agents/`: Retrieve a list of agents.
-   `GET /agents/{agent_id}`: Retrieve a specific agent by ID.

### Customer Dimension

-   `POST /customers/`: Create a new customer.
-   `GET /customers/`: Retrieve a list of customers.
-   `GET /customers/{customer_id}`: Retrieve a specific customer by ID.

### Location Dimension

-   `POST /locations/`: Create a new location.
-   `GET /locations/`: Retrieve a list of locations.
-   `GET /locations/{location_id}`: Retrieve a specific location by ID.

### Transaction Fact

-   `POST /transactions/`: Create a new transaction.
-   `GET /transactions/`: Retrieve a list of transactions.
-   `GET /transactions/{transaction_uuid}`: Retrieve a specific transaction by UUID.

### Health Check

-   `GET /health`: Check the health status of the service and its dependencies.

## Error Handling

The service implements comprehensive error handling, returning appropriate HTTP status codes and detailed error messages for issues such as:

-   **401 Unauthorized**: Invalid or missing authentication token.
-   **404 Not Found**: Resource not found.
-   **409 Conflict**: Resource with the given ID already exists (e.g., creating an agent with an existing `agent_id`).
-   **500 Internal Server Error**: Unexpected server-side errors.

## Logging and Monitoring

Logs are configured to output to standard output, with the level configurable via the `LOG_LEVEL` environment variable. For production deployments, integrate with a centralized logging solution (e.g., ELK stack, Splunk, Datadog).

## Security Considerations

-   **Authentication**: JWT-based authentication is implemented. Ensure `SECRET_KEY` is strong and kept confidential.
-   **Authorization**: All data access endpoints require a valid access token.
-   **Input Validation**: Pydantic models ensure all incoming data is validated.
-   **SQL Injection**: SQLAlchemy ORM protects against SQL injection attacks.
-   **Sensitive Data**: Avoid logging sensitive information directly. Mask or redact as necessary.

## Future Enhancements

-   **Metrics**: Integration with Prometheus/Grafana for detailed service metrics.
-   **Tracing**: Distributed tracing with OpenTelemetry.
-   **Asynchronous Tasks**: Using Celery or similar for background processing.
-   **Advanced Authorization**: Role-Based Access Control (RBAC).
-   **Database Migrations**: Using Alembic for managing database schema changes.
-   **Unit and Integration Tests**: Comprehensive test suite.

## License

This project is licensed under the MIT License.

