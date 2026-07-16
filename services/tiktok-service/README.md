# Tiktok Service

TikTok Shop integration

## Features

- ✅ Send messages via Tiktok
- ✅ Receive webhooks from Tiktok
- ✅ Order management
- ✅ Message tracking
- ✅ Delivery confirmations
- ✅ Production-ready with proper error handling

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set these environment variables:

```bash
export TIKTOK_API_KEY="your_api_key"
export TIKTOK_API_SECRET="your_api_secret"
export TIKTOK_WEBHOOK_SECRET="your_webhook_secret"
export PORT=8094
```

## Running

```bash
python main.py
```

## API Documentation

Visit `http://localhost:8094/docs` for interactive API documentation.

## API Endpoints

### Core Endpoints
- `GET /` - Service information
- `GET /health` - Health check
- `GET /api/v1/metrics` - Service metrics

### Messaging
- `POST /api/v1/send` - Send a message
- `GET /api/v1/messages` - Get message history
- `POST /webhook` - Webhook endpoint for incoming messages

### Orders
- `POST /api/v1/order` - Create an order
- `GET /api/v1/orders` - Get orders

## Example Usage

### Send a Message

```bash
curl -X POST http://localhost:8094/api/v1/send \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "+1234567890",
    "message_type": "text",
    "content": "Hello from Tiktok!"
  }'
```

### Create an Order

```bash
curl -X POST http://localhost:8094/api/v1/order \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST123",
    "customer_name": "John Doe",
    "phone": "+1234567890",
    "items": [{"name": "Product 1", "quantity": 2, "price": 50}],
    "total": 100.00,
    "delivery_address": "123 Main St"
  }'
```

## Integration with Unified Communication Hub

This service integrates with the Unified Communication Hub at:
`http://localhost:8060/api/v1/send`

The hub will automatically route messages through this channel when appropriate.
