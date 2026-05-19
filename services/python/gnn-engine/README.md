# GNN Engine Service for Remittance Platform

## Overview

This service is a core component of the Remittance Platform, designed to detect financial fraud using Graph Neural Networks (GNNs). It provides a robust, production-ready FastAPI application with comprehensive features including API endpoints for fraud detection, database integration, authentication, error handling, logging, configuration management, health checks, and metrics.

## Features

- **Fraud Detection**: Utilizes a simulated GNN model to predict fraudulent transactions.
- **RESTful API**: Exposes endpoints for creating, retrieving, updating, and deleting fraud events.
- **Database Integration**: Persists fraud event data and GNN analysis results using SQLAlchemy.
- **Authentication**: Secures API endpoints using API Key authentication.
- **Error Handling**: Comprehensive error handling for robust operation.
- **Logging**: Structured logging for monitoring and debugging.
- **Configuration Management**: Environment-based configuration using `pydantic-settings`.
- **Health Checks**: Endpoint to monitor service and database health.
- **Metrics**: Basic metrics endpoint for monitoring service performance.
- **API Documentation**: Automatic interactive API documentation via Swagger UI (`/docs`) and ReDoc (`/redoc`).

## Architecture

The service follows a layered architecture:

1.  **Presentation Layer**: FastAPI handles API requests and responses.
2.  **Business Logic Layer**: The `GNNModel` class encapsulates the fraud detection logic (simulated).
3.  **Data Access Layer**: SQLAlchemy manages interactions with the PostgreSQL database (or SQLite for development).
4.  **Cross-Cutting Concerns**: Middleware for authentication, logging, and error handling.

## Setup and Installation

### Prerequisites

- Python 3.9+
- `pip` (Python package installer)
- A PostgreSQL database (recommended for production) or SQLite (for local development)

### 1. Clone the Repository

```bash
git clone <repository_url>
cd gnn-engine
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

### 4. Configuration

Create a `.env` file in the root directory of the project based on `config.py`:

```dotenv
DATABASE_URL="postgresql://user:password@host:port/database_name" # e.g., sqlite:///./sql_app.db
API_KEY="your_super_secret_api_key"
LOG_LEVEL="INFO"
```

**Note**: For production, it's recommended to manage environment variables securely (e.g., Kubernetes secrets, AWS Secrets Manager).

### 5. Run the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag is useful for development as it restarts the server on code changes.

## API Endpoints

The API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) once the application is running.

### Health Checks & Monitoring

- `GET /`: Root endpoint, returns a welcome message.
- `GET /health`: Checks the service and database connection status.
- `GET /metrics`: Provides basic service metrics (placeholder).

### Fraud Detection

- `POST /fraud-events/detect`: Submits a new fraud event for GNN detection and stores the results.
  - Request Body: `FraudEventCreate` schema
  - Response: `FraudEventWithAnalysisResponse` schema
- `GET /fraud-events/{event_id}`: Retrieves a fraud event by its ID.
- `GET /fraud-events/transaction/{transaction_id}`: Retrieves a fraud event by its transaction ID.
- `GET /fraud-events/user/{user_id}`: Retrieves all fraud events associated with a specific user ID.
- `GET /fraud-events`: Retrieves a list of all fraud events, with optional filtering by `is_fraudulent` status.
- `PUT /fraud-events/{event_id}`: Updates an existing fraud event by ID.
  - Request Body: `FraudEventUpdate` schema
  - Response: `FraudEventResponse` schema
- `DELETE /fraud-events/{event_id}`: Deletes a fraud event and its associated GNN analysis results by ID.

## Security

API access is secured using an `X-API-Key` header. Ensure your API key is strong and kept confidential.

## Logging

Logs are configured to output to the console with `INFO` level by default. The log level can be configured via the `LOG_LEVEL` environment variable.

## Extending the GNN Model

The `GNNModel` class in `main.py` currently contains a simulated prediction logic. To integrate a real GNN model:

1.  **Load Model**: Replace the placeholder with actual model loading logic (e.g., `torch.load` for PyTorch Geometric models).
2.  **Data Preprocessing**: Implement graph construction and feature extraction from incoming `FraudEventCreate` data, potentially integrating with Redis or other data sources for real-time features.
3.  **Inference**: Run the loaded GNN model for prediction.
4.  **Post-processing**: Interpret model outputs to determine `is_fraudulent`, `fraud_score`, and extract `node_features`, `edge_features`, `graph_embedding`, and `anomalous_nodes`.

## Contributing

Contributions are welcome! Please follow standard Git Flow for feature development and bug fixes.

## License

This project is licensed under the MIT License - see the LICENSE file for details. (Note: A `LICENSE` file is not provided in this example, but should be included in a real project.)

