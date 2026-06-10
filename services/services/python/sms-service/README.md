# SMS Service API

This document provides a comprehensive guide to the SMS Service API, a FastAPI-based microservice designed for sending and managing SMS messages within the Remittance Platform.

## Features

-   **User Authentication & Authorization**: Secure access to API endpoints using JWT tokens.
-   **SMS Sending**: Endpoint to send SMS messages to specified recipients.
-   **Message Status Retrieval**: Endpoint to check the status of previously sent SMS messages.
-   **Database Integration**: Utilizes PostgreSQL for persistent storage of user and message data.
-   **Configuration Management**: Environment-based configuration using `pydantic-settings`.
-   **Health Checks**: Endpoint to monitor the service's operational status.
-   **Comprehensive Logging**: Structured logging for better observability and debugging.
-   **API Documentation**: Automatic interactive API documentation via Swagger UI (`/docs`) and ReDoc (`/redoc`).

## Technologies Used

-   **FastAPI**: High-performance web framework for building APIs.
-   **SQLAlchemy**: ORM for interacting with PostgreSQL database.
-   **Pydantic**: Data validation and settings management.
-   **Passlib**: Hashing passwords.
-   **Python-jose**: JWT token handling.

## Setup and Installation

### Prerequisites

-   Python 3.9+
-   Docker (recommended for local development with PostgreSQL and Redis)

### 1. Clone the Repository

```bash
git clone <repository_url>
cd sms-service
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory of the service based on `config.py`. Example:

```ini
DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/sms_service_db"
SECRET_KEY="your-super-secret-jwt-key"
LOG_LEVEL="INFO"
SMS_PROVIDER_API_KEY="your_sms_provider_api_key"
SMS_PROVIDER_API_SECRET="your_sms_provider_api_secret"
SMS_PROVIDER_BASE_URL="https://api.example-sms-provider.com"
```

**Note**: For production, manage these environment variables securely (e.g., Kubernetes secrets, AWS Secrets Manager).

### 5. Database Setup

Ensure a PostgreSQL database is running and accessible via the `DATABASE_URL` specified in your `.env` file. The application will automatically create tables on startup if they don't exist.

### 6. Running the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be accessible at `http://localhost:8000`.

## API Endpoints

### Authentication

-   **POST `/token`**
    -   **Description**: Authenticate a user and obtain an access token.
    -   **Request Body**: `username` (form data), `password` (form data)
    -   **Response**: `Token` (access_token, token_type)

-   **POST `/users/`**
    -   **Description**: Register a new user.
    -   **Request Body**: `UserCreate` (username, password)
    -   **Response**: `UserResponse` (id, username, is_active)

-   **GET `/users/me/`**
    -   **Description**: Retrieve information about the current authenticated user.
    -   **Authorization**: Bearer Token required.
    -   **Response**: `UserResponse` (id, username, is_active)

### SMS Operations

-   **POST `/sms/send`**
    -   **Description**: Send an SMS message.
    -   **Authorization**: Bearer Token required.
    -   **Request Body**: `MessageCreate` (sender, recipient, content)
    -   **Response**: `MessageResponse` (id, sender, recipient, content, status, created_at, sent_at, delivery_report)

-   **GET `/sms/{message_id}`**
    -   **Description**: Get the status and details of a specific SMS message.
    -   **Authorization**: Bearer Token required.
    -   **Path Parameter**: `message_id` (integer)
    -   **Response**: `MessageResponse` (id, sender, recipient, content, status, created_at, sent_at, delivery_report)

### Health Check

-   **GET `/health`**
    -   **Description**: Check the health status of the service and its dependencies.
    -   **Response**: `{"status": "ok", "database": "connected"}` or error details.

## Error Handling

The API provides consistent error responses for various scenarios:

-   `401 Unauthorized`: Invalid or missing authentication credentials.
-   `400 Bad Request`: Invalid input or existing resource (e.g., username already registered).
-   `404 Not Found`: Resource not found (e.g., message ID not found).
-   `500 Internal Server Error`: Unexpected server-side errors.
-   `503 Service Unavailable`: Dependent services (e.g., database) are unreachable.

## Logging and Monitoring

Logs are configured to output to standard output with `INFO` level by default, configurable via the `LOG_LEVEL` environment variable. For production deployments, integrate with a centralized logging solution (e.g., ELK stack, Splunk).

## Security Considerations

-   **JWT Secret Key**: Ensure `SECRET_KEY` is a strong, randomly generated string and kept confidential.
-   **Password Hashing**: User passwords are hashed using `bcrypt`.
-   **Environment Variables**: Sensitive information like database credentials and API keys should be managed via environment variables and not hardcoded.
-   **HTTPS**: Deploy the service behind a reverse proxy (e.g., Nginx, Traefik) with HTTPS enabled for all traffic.

## Future Enhancements

-   Integration with a real SMS Gateway provider (e.g., Twilio, Nexmo).
-   Asynchronous message sending using a task queue (e.g., Celery with Redis).
-   More robust error handling for external API calls with retry mechanisms.
-   Detailed metrics collection and exposure (e.g., Prometheus).
-   Containerization with Docker and orchestration with Kubernetes for scalable deployments.

