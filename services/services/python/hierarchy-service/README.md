# Hierarchy Service API

## Overview

This service provides a robust and scalable API for managing hierarchical structures within the Remittance Platform. It is built using FastAPI, SQLAlchemy, and PostgreSQL, designed for production readiness with comprehensive error handling, logging, authentication, and API documentation.

## Features

- **Hierarchy Node Management**: Create, read, update, and delete hierarchical nodes.
- **Parent/Child Relationships**: Establish and manage relationships between nodes.
- **Authentication & Authorization**: Secure API access using OAuth2 (placeholder for integration).
- **Configuration Management**: Environment-based configuration using `pydantic-settings`.
- **Health Checks**: Endpoint for monitoring service health.
- **Comprehensive Logging**: Detailed logging for operational insights and debugging.
- **Database Integration**: PostgreSQL integration via SQLAlchemy.

## API Endpoints

The following endpoints are available:

| HTTP Method | Path                                   | Description                                       | Authentication Required |
| :---------- | :------------------------------------- | :------------------------------------------------ | :---------------------- |
| `POST`      | `/nodes/`                              | Create a new hierarchy node.                      | Yes                     |
| `GET`       | `/nodes/`                              | Retrieve a list of all hierarchy nodes.           | Yes                     |
| `GET`       | `/nodes/{node_id}`                     | Retrieve a specific hierarchy node by ID.         | Yes                     |
| `PUT`       | `/nodes/{node_id}`                     | Update an existing hierarchy node.                | Yes                     |
| `DELETE`    | `/nodes/{node_id}`                     | Delete a hierarchy node.                          | Yes                     |
| `GET`       | `/nodes/{node_id}/children`            | Get children of a specific node.                  | Yes                     |
| `GET`       | `/nodes/{node_id}/parent`              | Get parent of a specific node.                    | Yes                     |
| `POST`      | `/nodes/{node_id}/assign_parent/{parent_id}` | Assign a parent to a node.                        | Yes                     |
| `POST`      | `/nodes/{node_id}/remove_parent`       | Remove parent from a node.                        | Yes                     |
| `GET`       | `/health`                              | Check the health status of the service.           | No                      |

Full interactive API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the service is running.

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL database
- `pip` package manager

### 1. Clone the repository

```bash
git clone <repository_url>
cd hierarchy-service
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the root directory of the service based on the `config.py` file. This file will hold your environment-specific configurations.

Example `.env`:

```dotenv
APP_NAME="Hierarchy Service"
DATABASE_URL="postgresql://user:password@localhost:5432/hierarchy_db"
SECRET_KEY="your-super-secret-key-for-jwt"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Note**: Replace `your-super-secret-key-for-jwt` with a strong, randomly generated secret key in a production environment.

### 4. Run Database Migrations (if applicable)

This service uses SQLAlchemy with `Base.metadata.create_all(bind=engine)` for initial table creation on startup. For production environments, consider using a dedicated migration tool like Alembic for managing database schema changes.

### 5. Run the service

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag is useful for development; remove it for production deployments.

The API will be accessible at `http://localhost:8000`.

## Security

- **Authentication**: The service uses OAuth2 Password Bearer for token-based authentication. In a production setup, integrate with an identity provider (e.g., Keycloak, Auth0) for robust token validation and user management.
- **Authorization**: Implement fine-grained authorization logic based on user roles and permissions within the `get_current_user` dependency or specific endpoint logic.
- **Secret Management**: Store sensitive information (like `SECRET_KEY` and `DATABASE_URL`) securely using environment variables or a dedicated secret management service (e.g., AWS Secrets Manager, HashiCorp Vault).
- **Input Validation**: FastAPI models (Pydantic) automatically handle input validation, but additional business logic validation should be implemented where necessary.

## Logging and Monitoring

- **Logging**: The service uses Python's standard `logging` module. Logs are configured to output to `stdout`, which can be captured by container orchestration systems (e.g., Kubernetes) and forwarded to centralized logging solutions (e.g., ELK Stack, Datadog).
- **Metrics**: Integrate with Prometheus/Grafana for custom metrics to monitor API performance, error rates, and resource utilization. (Not explicitly implemented in this basic version, but recommended for production).
- **Health Checks**: The `/health` endpoint provides a basic health check. For more advanced monitoring, integrate with readiness and liveness probes in containerized environments.

## Error Handling

Global exception handlers are implemented for `HTTPException` and `SQLAlchemyError` to provide consistent error responses and log critical issues. Specific error handling for business logic should be implemented within individual endpoint functions.

## Contributing

(Instructions for contributing to the project, if applicable.)

## License

(Specify the license under which the project is distributed.)

