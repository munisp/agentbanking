# Remittance Platform DB Service

## Overview

This project implements a complete, production-ready FastAPI database service for an Remittance Platform. It provides RESTful APIs for managing agents, customers, accounts, and transactions. The service is designed with best practices in mind, including robust error handling, logging, authentication, and configuration management.

## Features

- **Agent Management**: CRUD operations for banking agents.
- **Customer Management**: CRUD operations for customers.
- **Account Management**: CRUD operations for customer accounts, linked to agents and customers.
- **Transaction Management**: CRUD operations for financial transactions, linked to accounts, agents, and customers.
- **Authentication**: API Key-based authentication for secure access.
- **Error Handling**: Comprehensive error handling with appropriate HTTP status codes and logging.
- **Logging**: Structured logging for monitoring and debugging.
- **Configuration Management**: Environment variable-based configuration using `python-dotenv`.
- **Health Checks**: Endpoint to monitor the service and database health.
- **Metrics (Placeholder)**: An endpoint for exposing metrics (can be extended for Prometheus integration).
- **API Documentation**: Automatic interactive API documentation using Swagger UI (ReDoc also available).

## Technologies Used

- **FastAPI**: High-performance web framework for building APIs.
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapper (ORM) for database interaction.
- **Pydantic**: Data validation and settings management using Python type hints.
- **SQLite**: Default database for development (easily configurable for PostgreSQL or other production databases).
- **Uvicorn**: ASGI server for running the FastAPI application.
- **python-dotenv**: For managing environment variables.

## Setup and Installation

### Prerequisites

- Python 3.9+
- `pip` (Python package installer)

### 1. Clone the repository

```bash
git clone <repository_url>
cd remittance_db_service
```

### 2. Create a virtual environment and activate it

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configuration

Create a `.env` file in the root directory of the project based on `config.py`:

```
DATABASE_URL="sqlite:///./sql_app.db"
SECRET_KEY="your-super-secret-key-here"
API_KEY="your-api-key-for-authentication"
LOG_LEVEL="INFO"
```

**Note**: For production, replace `sqlite:///./sql_app.db` with your PostgreSQL connection string (e.g., `postgresql://user:password@host:port/dbname`) and generate strong, unique `SECRET_KEY` and `API_KEY` values.

### 5. Run the application

```bash
uvicorn main:app --reload
```

The application will be accessible at `http://127.0.0.1:8000`.

## API Documentation

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## API Endpoints

All endpoints require an `X-API-Key` header for authentication.

### Health Check

- `GET /`: Returns a welcome message.
- `GET /health`: Checks the service and database connectivity.

### Agents

- `POST /agents/`: Create a new agent.
- `GET /agents/`: Retrieve a list of agents.
- `GET /agents/{agent_id}`: Retrieve a single agent by ID.
- `PUT /agents/{agent_id}`: Update an existing agent.
- `DELETE /agents/{agent_id}`: Delete an agent.

### Customers

- `POST /customers/`: Create a new customer.
- `GET /customers/`: Retrieve a list of customers.
- `GET /customers/{customer_id}`: Retrieve a single customer by ID.
- `PUT /customers/{customer_id}`: Update an existing customer.
- `DELETE /customers/{customer_id}`: Delete a customer.

### Accounts

- `POST /accounts/`: Create a new account.
- `GET /accounts/`: Retrieve a list of accounts.
- `GET /accounts/{account_number}`: Retrieve a single account by number.
- `PUT /accounts/{account_number}`: Update an existing account.
- `DELETE /accounts/{account_number}`: Delete an account.

### Transactions

- `POST /transactions/`: Create a new transaction.
- `GET /transactions/`: Retrieve a list of transactions.
- `GET /transactions/{transaction_id}`: Retrieve a single transaction by ID.
- `PUT /transactions/{transaction_id}`: Update an existing transaction.
- `DELETE /transactions/{transaction_id}`: Delete a transaction.

## Error Handling

The service provides consistent error responses in JSON format, for example:

```json
{
  "message": "Agent not found"
}
```

Common error codes include:
- `400 Bad Request`: Invalid input or existing resource.
- `401 Unauthorized`: Missing or invalid API Key.
- `404 Not Found`: Resource not found.
- `500 Internal Server Error`: Unexpected server error.

## Logging

Logs are output to the console and can be configured via the `LOG_LEVEL` environment variable (`INFO`, `WARNING`, `ERROR`, etc.).

## Security Considerations

- **API Keys**: Ensure `API_KEY` is kept secret and rotated regularly.
- **Database Credentials**: Store `DATABASE_URL` securely, preferably using a secrets management service in production.
- **Input Validation**: Pydantic models ensure robust input validation.
- **Dependency Updates**: Regularly update dependencies to patch known vulnerabilities.

## Contributing

Feel free to fork the repository, open issues, and submit pull requests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details. (Note: `LICENSE` file is not included in this task, but would be in a real project.)

