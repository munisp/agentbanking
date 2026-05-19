# Tigerbeetle Core

TigerBeetle core accounting service

## Features

- RESTful API
- Health checks
- Metrics endpoint
- High performance
- Production-ready

## Running

```bash
go run main.go
```

## API Endpoints

- `GET /` - Service information
- `GET /health` - Health check
- `GET /api/v1/status` - Service status
- `GET /api/v1/metrics` - Service metrics

## Environment Variables

- `PORT` - Service port (default: 8080)
