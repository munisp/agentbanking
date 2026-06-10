# Edge Deployment Service

This service manages the deployment and lifecycle of edge devices within the Remittance Platform. It provides APIs for registering devices, initiating and tracking deployments, and monitoring device health.

## Features

- **Device Management**: Register, retrieve, update, and delete edge device records.
- **Deployment Management**: Initiate and track software/configuration deployments to edge devices.
- **Authentication & Authorization**: Secure API access using JWT tokens, with role-based access for administrative tasks.
- **Health Checks**: Endpoint to monitor service availability.
- **Metrics**: Prometheus metrics for monitoring service performance.
- **Configuration Management**: Externalized configuration using environment variables.
- **Database Integration**: PostgreSQL for persistent storage of device and deployment data.

## Technologies Used

- FastAPI
- SQLAlchemy (for ORM)
- PostgreSQL (database)
- Pydantic (data validation and serialization)
- python-jose (JWT)
- passlib (password hashing)
- prometheus-fastapi-instrumentator (Prometheus metrics)
- pydantic-settings (configuration management)

## Setup and Installation

1.  **Clone the repository**:

    ```bash
    git clone <repository_url>
    cd edge_deployment_service
    ```

2.  **Create a virtual environment**:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Setup**:

    Ensure you have a PostgreSQL database running. Create a database for this service.

    Set the `DATABASE_URL` environment variable or in a `.env` file:

    ```
    DATABASE_URL="postgresql://user:password@host:port/dbname"
    ```

    The service will automatically create tables on startup if they don't exist.

5.  **Configuration**:

    Create a `.env` file in the root of the `edge_deployment_service` directory with the following variables:

    ```
    DATABASE_URL="postgresql://user:password@localhost:5432/edgedb"
    SECRET_KEY="your-super-secret-jwt-key"
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    LOG_LEVEL="INFO"
    ```

    **Important**: Change `SECRET_KEY` to a strong, random value in production.

6.  **Run the application**:

    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```

    The API documentation will be available at `http://localhost:8000/docs`.

## API Endpoints

Refer to the automatically generated OpenAPI documentation at `/docs` for detailed information on all available endpoints, request/response schemas, and authentication requirements.

### Authentication

-   `POST /token`: Obtain an access token using username and password.
-   `POST /users/`: Register a new user.
-   `GET /users/me/`: Get information about the current authenticated user.

### Edge Devices

-   `POST /devices/`: Register a new edge device.
-   `GET /devices/`: Retrieve a list of all edge devices.
-   `GET /devices/{device_id}`: Retrieve details of a specific edge device.
-   `PUT /devices/{device_id}`: Update an existing edge device.
-   `DELETE /devices/{device_id}`: Delete an edge device (admin only).

### Deployments

-   `POST /deployments/`: Initiate a new deployment.
-   `GET /deployments/`: Retrieve a list of all deployments.
-   `GET /deployments/{deployment_id}`: Retrieve details of a specific deployment.
-   `PUT /deployments/{deployment_id}`: Update an existing deployment.
-   `DELETE /deployments/{deployment_id}`: Delete a deployment (admin only).

### Health & Metrics

-   `GET /health`: Check the health status of the service.
-   `GET /metrics`: Prometheus metrics endpoint.

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of a request. Detailed error messages are provided in the response body for client-side debugging.

## Logging

Logs are output to standard output (stdout) and can be configured via the `LOG_LEVEL` environment variable. Recommended for production environments to integrate with a centralized logging solution.

## Security

-   **JWT Authentication**: All sensitive endpoints require a valid JWT access token.
-   **Password Hashing**: User passwords are securely hashed using bcrypt.
-   **Role-Based Access Control**: Certain operations (e.g., deleting devices/deployments) are restricted to admin users.
-   **Environment Variables**: Sensitive configurations like `SECRET_KEY` and `DATABASE_URL` are loaded from environment variables.

## Contributing

(Add contributing guidelines here)

## License

(Add license information here)

