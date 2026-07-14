# ETL Pipeline Service for Remittance Platform

## Overview

This service provides a robust and scalable **Extract, Transform, Load (ETL) pipeline** for the Remittance Platform. It is built using FastAPI, SQLAlchemy for database interactions, and Pydantic for data validation and serialization. The service includes features such as user authentication, ETL job management, and background task processing for ETL operations.

## Features

- **User Authentication & Authorization**: Secure access to API endpoints using JWT tokens.
- **ETL Job Management**: Create, retrieve, update, and delete ETL jobs.
- **ETL Task Tracking**: Monitor the status and logs of individual ETL tasks within a job.
- **Background Processing**: Execute ETL jobs asynchronously to prevent blocking the API.
- **Database Integration**: PostgreSQL integration via SQLAlchemy.
- **S3 Integration**: Placeholder for S3 interactions (e.g., for source/destination data).
- **Configuration Management**: Environment-based configuration using `pydantic-settings`.
- **Logging**: Structured logging with `loguru`.
- **Health Checks**: Endpoint to monitor service availability.
- **API Documentation**: Interactive API documentation via Swagger UI (`/docs`) and ReDoc (`/redoc`).

## Technology Stack

- **Framework**: FastAPI
- **Database ORM**: SQLAlchemy
- **Database**: PostgreSQL (via `psycopg2-binary`)
- **Data Validation**: Pydantic
- **Authentication**: JWT (JSON Web Tokens) with `python-jose` and `passlib`
- **Cloud Storage**: AWS S3 (via `boto3`)
- **Logging**: `loguru`
- **Environment Management**: `pydantic-settings`

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL database instance
- AWS S3 bucket (optional, for actual S3 operations)
- Redis instance (optional, for future enhancements)

### 1. Clone the repository

```bash
git clone <repository_url>
cd etl_pipeline
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory of the service with the following variables:

```env
DATABASE_URL="postgresql://user:password@host:port/dbname"
AWS_ACCESS_KEY_ID="your_aws_access_key_id"
AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key"
AWS_REGION="us-east-1"
S3_BUCKET_NAME="your-s3-bucket-name"
SECRET_KEY="your-super-secret-jwt-key"
ACCESS_TOKEN_EXPIRE_MINUTES=30
LOG_LEVEL="INFO"
ENVIRONMENT="development"
DEBUG=True
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0
```

**Note**: Replace placeholder values with your actual credentials and settings. The `SECRET_KEY` should be a strong, randomly generated string.

### 4. Run Database Migrations (or create tables)

Ensure your PostgreSQL database is running. The application will attempt to create tables on startup if they don't exist. For production, consider using a proper migration tool like Alembic.

### 5. Run the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be accessible at `http://localhost:8000`.

## API Endpoints

The interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

### Authentication

- `POST /auth/token`: Obtain an access token using username and password.

### Users

- `POST /users/`: Register a new user.
- `GET /users/me/`: Get details of the current authenticated user.

### ETL Jobs

- `POST /etl-jobs/`: Create a new ETL job.
- `GET /etl-jobs/`: Retrieve a list of all ETL jobs for the current user.
- `GET /etl-jobs/{job_id}`: Retrieve details of a specific ETL job.
- `PUT /etl-jobs/{job_id}`: Update an existing ETL job.
- `DELETE /etl-jobs/{job_id}`: Delete an ETL job.
- `POST /etl-jobs/{job_id}/run`: Trigger an ETL job to run in the background.

### ETL Tasks

- `POST /etl-jobs/{job_id}/tasks/`: Create a new ETL task for a specific job.
- `GET /etl-jobs/{job_id}/tasks/`: Retrieve all tasks for a specific ETL job.
- `GET /etl-jobs/{job_id}/tasks/{task_id}`: Retrieve details of a specific ETL task.
- `PUT /etl-jobs/{job_id}/tasks/{task_id}`: Update an existing ETL task.
- `DELETE /etl-jobs/{job_id}/tasks/{task_id}`: Delete an ETL task.

### Health Check

- `GET /health`: Check the health status of the service.

## Error Handling

The service provides comprehensive error handling for common scenarios, returning appropriate HTTP status codes and detailed error messages. Examples include:

- `401 Unauthorized`: Invalid or missing authentication credentials.
- `400 Bad Request`: Invalid input data or business rule violations (e.g., username already registered).
- `404 Not Found`: Resource not found.
- `409 Conflict`: Resource state conflict (e.g., trying to run an already running ETL job).
- `500 Internal Server Error`: Unexpected server errors.

## Logging and Monitoring

Logs are configured using `loguru` and output to `file.log` (configurable). The `LOG_LEVEL` can be set in the `.env` file. For production, integrate with a centralized logging solution.

## Security Best Practices

- **JWT Authentication**: Securely generated and managed JWT tokens.
- **Password Hashing**: Passwords are hashed using `bcrypt`.
- **Environment Variables**: Sensitive information is loaded from environment variables, not hardcoded.
- **Input Validation**: Pydantic models ensure all incoming data is validated.

## Extending the ETL Logic

The `run_etl_process` function in `main.py` currently simulates ETL tasks. To extend this:

1.  **Implement actual extraction**: Integrate with data sources (e.g., read from S3, call external APIs).
2.  **Implement actual transformation**: Apply business logic to transform the extracted data.
3.  **Implement actual loading**: Write transformed data to destinations (e.g., PostgreSQL, S3).
4.  **Error Handling**: Add more granular error handling and retry mechanisms within the ETL process.
5.  **Task Orchestration**: For complex ETL workflows, consider integrating with tools like Apache Airflow or Prefect.

## Contributing

Feel free to fork the repository, open issues, and submit pull requests.

## License

This project is licensed under the MIT License.
