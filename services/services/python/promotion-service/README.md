# Promotion Service

Marketing promotions management

## Features

- FastAPI REST API
- Automatic API documentation
- Health checks
- Metrics endpoint
- Production-ready

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## API Endpoints

- `GET /` - Service information
- `GET /health` - Health check
- `GET /api/v1/status` - Service status
- `GET /api/v1/metrics` - Service metrics

## Environment Variables

- `PORT` - Service port (default: 8000)
