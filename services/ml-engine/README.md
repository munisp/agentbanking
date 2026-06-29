# ML Engine Service

## Overview

This is a production-ready FastAPI service for the Remittance Platform, designed to manage and serve Machine Learning models and predictions. It includes comprehensive features such as API key authentication, logging, configuration management, and Prometheus metrics.

## Features

- **FastAPI Framework**: High-performance web framework for building APIs.
- **Database Integration**: SQLAlchemy ORM with PostgreSQL for managing ML models and prediction records.
- **Pydantic Models**: Data validation and serialization.
- **API Key Authentication**: Secure access to API endpoints.
- **Structured Logging**: Centralized logging for better observability.
- **Configuration Management**: Environment variable-based configuration using `pydantic-settings`.
- **Health Checks**: `/health` endpoint to monitor service status.
- **Prometheus Metrics**: `/metrics` endpoint for monitoring request count and latency.
- **Automatic API Documentation**: Swagger UI and ReDoc generated automatically by FastAPI.

## Project Structure

```
ml-engine/
├── main.py
├── models.py
├── schemas.py
├── database.py
├── security.py
├── config.py
├── metrics.py
└── requirements.txt
└── README.md
```

- `main.py`: The main FastAPI application, defining endpoints and integrating all components.
- `models.py`: SQLAlchemy models for `MLModel` and `Prediction`.
- `schemas.py`: Pydantic schemas for request and response validation.
- `database.py`: Database connection setup and session management.
- `security.py`: API key authentication logic.
- `config.py`: Application settings loaded from environment variables or `.env` file.
- `metrics.py`: Prometheus metrics definitions.
- `requirements.txt`: Python dependencies.
- `README.md`: This documentation file.

## Setup and Installation

### Prerequisites

- Python 3.8+
- PostgreSQL database

### 1. Clone the repository (if applicable)

```bash
git clone <repository-url>
cd ml-engine
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Database Setup

Ensure you have a PostgreSQL database running. Create a database named `ml_engine_db` (or configure `DATABASE_URL` in your `.env` file).

### 4. Configuration

Create a `.env` file in the `ml-engine/` directory with the following content:

```dotenv
DATABASE_URL="postgresql://user:password@db:5432/ml_engine_db"
API_KEY="your_super_secret_api_key"
SECRET_KEY="your_super_secret_key_for_auth"
LOG_LEVEL="INFO"
```

Replace `user`, `password`, `db`, `your_super_secret_api_key`, and `your_super_secret_key_for_auth` with your actual database credentials and desired API key/secret key.

### 5. Run the application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be accessible at `http://0.0.0.0:8000`.

## API Documentation

Access the interactive API documentation (Swagger UI) at `http://0.0.0.0:8000/docs`.
Access the alternative API documentation (ReDoc) at `http://0.0.0.0:8000/redoc`.

## Endpoints

### Health Check

- `GET /health`
  - Returns `{"status": "healthy"}`.

### ML Models (Requires `X-API-Key` header)

- `POST /models/`
  - Create a new ML model entry.
- `GET /models/`
  - Retrieve a list of all ML models.
- `GET /models/{model_id}`
  - Retrieve a specific ML model by ID.
- `PUT /models/{model_id}`
  - Update an existing ML model by ID.
- `DELETE /models/{model_id}`
  - Delete an ML model by ID.

### Predictions (Requires `X-API-Key` header)

- `POST /predictions/`
  - Create a new prediction record. (Note: This currently stores request data and a dummy result; actual ML inference logic would be integrated here).
- `GET /predictions/`
  - Retrieve a list of all prediction records.
- `GET /predictions/{prediction_id}`
  - Retrieve a specific prediction record by ID.

### Monitoring

- `GET /metrics`
  - Exposes Prometheus metrics for request count and latency.

## Error Handling

- Standard HTTP exceptions are raised for common errors (e.g., 404 Not Found, 403 Forbidden).
- Internal server errors (500) are caught and logged, providing generic error messages to clients to avoid exposing sensitive information.

## Logging

- Application logs are configured to output to standard output with `INFO` level by default.
- Log level can be configured via the `LOG_LEVEL` environment variable.

## Security

- All sensitive endpoints are protected by API key authentication.
- API keys should be treated as secrets and managed securely.

## Future Enhancements

- Integration with actual ML inference engines (e.g., TensorFlow Serving, TorchServe).
- Asynchronous task queues (e.g., Celery) for long-running prediction tasks.
- More sophisticated authentication/authorization (e.g., OAuth2, JWT).
- Integration with S3 for ML model artifact storage and retrieval.
- Advanced monitoring and alerting.

