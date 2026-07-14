# Network Operations Service - API Documentation

## Overview

The Network Operations Service predicts the likelihood of transaction success based on historical channel performance data for Nigerian banking and telecom providers.

## Endpoints

### 1. Register Transaction

**POST** `/api/v1/transactions`

Records a transaction attempt (success or failure) to update channel statistics.

**Request Body:**

```json
{
  "type": "transfer",
  "channel": "pos",
  "medium": "wema",
  "status": "success",
  "amount": 5000.0,
  "agent_id": "optional-uuid"
}
```

**Fields:**

- `type` (required): Transaction type
  - Banking: `transfer`, `withdrawal`, `balance_inquiry`, `bill_payment`
  - Telecom: `airtime`, `data`
- `channel` (required): Channel used
  - `pos` - POS Terminal
  - `ussd` - USSD Code
  - `web` - Web Portal
  - `app` - Mobile App
- `medium` (required): Provider/bank name
  - Banks: `wema`, `gtbank`, `access`, `first_bank`, `zenith`, `uba`, `union_bank`
  - Telecoms: `mtn`, `airtel`, `glo`, `9mobile`
  - Utilities: `dstv`, `gotv`, `ekedc`, `ikedc`, `bet9ja`
- `status` (required): `success` or `failed`
- `amount` (optional): Transaction amount in Naira (NGN)
- `agent_id` (optional): Agent identifier

**Response:**

```json
{
  "id": "uuid",
  "type": "transfer",
  "channel": "pos",
  "medium": "wema",
  "status": "success",
  "amount": 5000.0,
  "registered_at": "2026-03-01T10:00:00Z",
  "message": "Transaction registered successfully",
  "current_success_rate": 92.5
}
```

### 2. Get Predictions

**GET** `/api/v1/predictions`

Returns success rate predictions for all channels or filtered by type/channel/medium.

**Query Parameters:**

- `type` (optional): Filter by transaction type
- `channel` (optional): Filter by channel
- `medium` (optional): Filter by specific provider

**Example Requests:**

```
GET /api/v1/predictions
GET /api/v1/predictions?type=transfer
GET /api/v1/predictions?channel=pos
GET /api/v1/predictions?medium=mtn
GET /api/v1/predictions?type=data&channel=app
```

**Response:**

```json
{
  "predictions": [
    {
      "name": "wema",
      "channel": "pos",
      "type": "transfer",
      "status": "92%",
      "rate": 92.0,
      "total_txns": 200,
      "confidence": "high"
    },
    {
      "name": "airtel",
      "channel": "app",
      "type": "data",
      "status": "99%",
      "rate": 99.0,
      "total_txns": 320,
      "confidence": "high"
    }
  ],
  "count": 2,
  "filtered_by": {
    "type": "transfer",
    "channel": "pos"
  }
}
```

**Prediction Object Fields:**

- `name`: Provider/bank name
- `channel`: Channel type (pos, ussd, web, app)
- `type`: Transaction type
- `status`: Success rate as percentage string (e.g., "92%")
- `rate`: Numeric success rate (0-100)
- `total_txns`: Total transactions recorded
- `confidence`: Confidence level based on sample size
  - `low`: < 10 transactions
  - `medium`: 10-49 transactions
  - `high`: >= 50 transactions

### 3. Health Check

**GET** `/health`

Returns service health status.

**Response:**

```json
{
  "status": "healthy",
  "service": "network-operations",
  "timestamp": "2026-03-01T10:00:00Z"
}
```

## Example Use Cases

### 1. Check Transfer Success Rates via POS

```bash
curl 'http://localhost:8080/api/v1/predictions?type=transfer&channel=pos'
```

### 2. Check MTN Data Purchase Success Rates

```bash
curl 'http://localhost:8080/api/v1/predictions?type=data&medium=mtn'
```

### 3. Register a Successful Transaction

```bash
curl -X POST http://localhost:8080/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "type": "transfer",
    "channel": "pos",
    "medium": "wema",
    "status": "success",
    "amount": 10000.00
  }'
```

### 4. Register a Failed Transaction

```bash
curl -X POST http://localhost:8080/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "type": "airtime",
    "channel": "ussd",
    "medium": "glo",
    "status": "failed"
  }'
```

## Database Schema

### transaction_records

Stores each individual transaction attempt for statistical analysis.

| Column     | Type      | Description                   |
| ---------- | --------- | ----------------------------- |
| id         | UUID      | Primary key                   |
| type       | VARCHAR   | Transaction type              |
| channel    | VARCHAR   | Channel used                  |
| medium     | VARCHAR   | Provider/bank name            |
| status     | VARCHAR   | success or failed             |
| amount     | DECIMAL   | Amount in Naira               |
| agent_id   | UUID      | Optional agent identifier     |
| created_at | TIMESTAMP | When transaction was recorded |

### channel_statistics

Aggregated statistics for prediction calculations.

| Column             | Type      | Description                       |
| ------------------ | --------- | --------------------------------- |
| id                 | UUID      | Primary key                       |
| type               | VARCHAR   | Transaction type                  |
| channel            | VARCHAR   | Channel name                      |
| medium             | VARCHAR   | Provider name                     |
| total_transactions | INT       | Total transaction count           |
| success_count      | INT       | Number of successful transactions |
| failure_count      | INT       | Number of failed transactions     |
| success_rate       | DECIMAL   | Success rate percentage (0-100)   |
| last_updated       | TIMESTAMP | Last statistics update            |

## Environment Variables

- `DB_HOST` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)
- `DB_NAME` - Database name (default: link_core_banking)
- `DB_USER` - Database user (default: postgres)
- `DB_PASSWORD` - Database password (default: password)
- `PORT` - Service port (default: 8080)

## Running the Service

1. **Start the service:**

```bash
cd /home/tani/Documents/54agent/54agent_agent_banking/services/network-operations
go run main.go
```

2. **Seed the database with mock data:**

```bash
go run seed_data.go
```

3. **Drop old tables (one-time migration):**

```bash
go run drop_old_tables.go
```

## Expected Success Rates (Mock Data)

### Banking Transactions

- **Mobile App**: 92-98% (highest success rate)
- **Web Portal**: 89-96% (very good)
- **POS Terminal**: 82-95% (good)
- **USSD**: 71-82% (variable)

### Telecom Transactions

- **MTN**: 94-100% (excellent)
- **Airtel**: 90-99% (very good)
- **Glo**: 82-96% (good)
- **9mobile**: 78-91% (fair)

### By Channel

- **Mobile App**: Generally highest success rates
- **Web Portal**: High success rates
- **POS**: Good success rates
- **USSD**: Most variable, lower success rates
