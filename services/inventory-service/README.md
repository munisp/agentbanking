# Inventory & POS Integration

This update syncs the inventory and POS terminal management between the UI and backend services.

## What Was Added

### 1. **New Inventory Service** (`services/inventory-service/`)

A FastAPI-based microservice for managing inventory and POS sales:

**Endpoints:**

- `GET /inventory/items` - List all inventory items (with filters)
- `GET /inventory/items/{id}` - Get specific item
- `POST /inventory/items` - Create new inventory item
- `PUT /inventory/items/{id}` - Update inventory item
- `DELETE /inventory/items/{id}` - Delete inventory item
- `GET /inventory/alerts` - Get low stock alerts
- `POST /inventory/sales` - Process sale and update inventory
- `GET /inventory/sales` - Get sales history
- `GET /inventory/metrics` - Get inventory metrics
- `GET /health` - Health check

**Features:**

- Automatic stock status tracking (in_stock, low_stock, critical, out_of_stock)
- VAT calculation (7.5%)
- Real-time inventory updates on sales
- PostgreSQL database integration
- Dapr sidecar support

### 2. **Updated UI Components**

#### InventoryManagement.tsx

- Integrated with real API endpoints
- Loads inventory items from backend
- Processes sales through API
- Real-time stock updates
- Sales history from database
- Proper error handling and loading states

#### POSManagement.tsx

- Connected to pos-terminal-management service
- Displays real terminal data
- Terminal status tracking
- Search and filter functionality

### 3. **API Client Updates** (`uis/admin-dashboard/src/utils/api.ts`)

Added comprehensive API methods:

- Inventory CRUD operations
- Sales management
- Stock alerts
- POS terminal management
- TypeScript interfaces for type safety

### 4. **Infrastructure**

**Helm Chart:** `infrastructure/charts/inventory-service/`

- Kubernetes deployment configuration
- Service definition
- Secrets management
- Dapr integration
- Resource limits and probes

**APISIX Route:** `infrastructure/apisix-resources/routes/inventory-service.yaml`

- Routes `/inventory/*` to inventory-service
- CORS enabled
- Path rewriting configured

## API Usage Examples

### Create Inventory Item

```bash
curl -X POST http://54agent.upi.dev/inventory/inventory/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "POS Terminal - Model A",
    "sku": "POS-A-001",
    "category": "Hardware",
    "quantity": 45,
    "reorder_level": 20,
    "unit_price": 25000,
    "supplier": "Tech Solutions Ltd",
    "location": "Warehouse A",
    "barcode": "1234567890123"
  }'
```

### Get All Inventory

```bash
curl http://54agent.upi.dev/inventory/inventory/items?status=low_stock \
  -H "Authorization: Bearer $TOKEN"
```

### Process Sale

```bash
curl -X POST http://54agent.upi.dev/inventory/inventory/sales \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "customer_name": "John Doe",
    "items": [
      {
        "name": "POS Terminal - Model A",
        "sku": "POS-A-001",
        "quantity": 2,
        "unit_price": 25000,
        "total": 50000
      }
    ]
  }'
```

### Get POS Terminals

```bash
curl http://54agent.upi.dev/pos-terminal/terminals \
  -H "Authorization: Bearer $TOKEN"
```

## Database Schema

### inventory_items Table

- `id` (serial, primary key)
- `name` (text)
- `sku` (text, unique)
- `category` (text)
- `quantity` (integer)
- `reorder_level` (integer)
- `unit_price` (float)
- `supplier` (text)
- `location` (text)
- `status` (text)
- `barcode` (text, unique)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### sales_records Table

- `id` (text, primary key)
- `customer_name` (text)
- `subtotal` (float)
- `tax` (float)
- `total` (float)
- `items` (jsonb)
- `created_at` (timestamp)

## Deployment

### Local Development

```bash
cd services/inventory-service
pip install -r requirements.txt
./run.sh
```

### Docker Build

```bash
cd services/inventory-service
docker build -t 54agent-inventory-service:0.0.1 .
```

### Kubernetes Deployment

```bash
# Install the Helm chart
helm install inventory-service infrastructure/charts/inventory-service \
  --namespace 54agent

# Apply APISIX route
kubectl apply -f infrastructure/apisix-resources/routes/inventory-service.yaml
```

## Environment Variables

Required for the inventory service:

- `DATABASE_URL` - PostgreSQL connection string
- `PORT` - Service port (default: 8096)

## Integration Points

1. **Admin Dashboard** → Inventory Service (CRUD operations)
2. **Admin Dashboard** → POS Terminal Management (terminal monitoring)
3. **Inventory Service** → PostgreSQL (data persistence)
4. **APISIX Gateway** → Route `/inventory/*` to inventory-service

## Next Steps

1. Update existing POS terminals in database
2. Seed initial inventory items
3. Configure authentication middleware in APISIX
4. Add analytics and reporting endpoints
5. Implement bulk import/export functionality
