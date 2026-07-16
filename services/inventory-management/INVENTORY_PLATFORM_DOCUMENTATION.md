# Comprehensive Inventory Management Platform

## Overview

The Inventory Management Platform is a robust B2B supply chain solution that integrates agents with manufacturers, provides credit facilities, and manages shipping and logistics. It's fully integrated into the Remittance Platform.

**Port**: 8027  
**Database**: PostgreSQL (remittance)  
**Cache**: Redis  
**API Style**: RESTful

---

## 🎯 Core Features

### 1. Manufacturer Integration
- Register and verify manufacturers
- Product catalog management
- Minimum order values and payment terms
- Lead time tracking
- Rating and review system

### 2. Inventory Management
- Real-time inventory tracking
- Automatic reorder alerts
- Low stock notifications
- Multi-manufacturer product catalog
- SKU management
- Specifications and images

### 3. Purchase Order System
- Create and manage purchase orders
- Order approval workflow
- Status tracking (Pending → Approved → Processing → Shipped → Delivered)
- Payment method selection (Credit, Bank Transfer, Mobile Money)
- Automatic inventory deduction

### 4. Credit Facilities
- Credit application and approval
- Credit score calculation
- Dynamic credit limit determination
- Interest rate based on credit score
- Credit utilization tracking
- Payment processing
- Transaction history

### 5. Shipping & Logistics
- Shipment creation and tracking
- Real-time location updates
- Estimated delivery dates
- Multiple logistics providers
- Tracking history
- Delivery confirmation

### 6. Analytics & Reporting
- Inventory value tracking
- Low stock alerts
- Active purchase orders
- Credit utilization analytics
- Top manufacturers by volume
- Dashboard metrics

---

## 📊 Database Schema

### Tables Created

1. **manufacturers** - Manufacturer registry
2. **inventory_products** - Product catalog
3. **purchase_orders** - Purchase order records
4. **credit_facilities** - Agent credit facilities
5. **shipments** - Shipment tracking
6. **logistics_providers** - Logistics provider registry
7. **inventory_alerts** - Stock alerts
8. **credit_transactions** - Credit transaction history

---

## 🔌 API Endpoints

### Manufacturer Endpoints

#### POST `/api/inventory/manufacturers`
Register a new manufacturer

**Request Body**:
```json
{
  "name": "ABC Manufacturing Ltd",
  "business_registration": "RC123456",
  "contact_person": "John Doe",
  "email": "john@abcmanufacturing.com",
  "phone": "+234-800-123-4567",
  "address": "123 Industrial Area, Lagos, Nigeria",
  "product_categories": ["Electronics", "Appliances"],
  "minimum_order_value": 50000.00,
  "payment_terms": "net_30",
  "lead_time_days": 7,
  "rating": 4.5,
  "verified": true
}
```

**Response**:
```json
{
  "id": "uuid",
  "created_at": "2025-10-13T10:00:00",
  "message": "Manufacturer registered successfully"
}
```

#### GET `/api/inventory/manufacturers`
Get all manufacturers with optional filters

**Query Parameters**:
- `category` (optional): Filter by product category
- `verified` (optional): Filter by verification status

**Response**: Array of manufacturer objects

#### GET `/api/inventory/manufacturers/{manufacturer_id}`
Get manufacturer details

---

### Inventory Product Endpoints

#### POST `/api/inventory/products`
Add a new product to inventory

**Request Body**:
```json
{
  "manufacturer_id": "uuid",
  "sku": "PROD-001",
  "name": "Smart TV 55 inch",
  "description": "4K Ultra HD Smart Television",
  "category": "Electronics",
  "unit_price": 250000.00,
  "wholesale_price": 200000.00,
  "minimum_order_quantity": 5,
  "available_quantity": 100,
  "reorder_level": 20,
  "unit_of_measure": "pieces",
  "specifications": {
    "screen_size": "55 inches",
    "resolution": "4K",
    "smart_features": true
  },
  "images": ["url1", "url2"]
}
```

#### GET `/api/inventory/products`
Get inventory products

**Query Parameters**:
- `manufacturer_id` (optional)
- `category` (optional)
- `low_stock` (optional): Boolean to filter low stock items

#### PUT `/api/inventory/products/{product_id}/quantity`
Update product quantity

**Request Body**:
```json
{
  "quantity": 10,
  "operation": "add"  // or "subtract" or "set"
}
```

---

### Purchase Order Endpoints

#### POST `/api/inventory/purchase-orders`
Create a new purchase order

**Request Body**:
```json
{
  "agent_id": "uuid",
  "manufacturer_id": "uuid",
  "items": [
    {
      "product_id": "uuid",
      "product_name": "Smart TV 55 inch",
      "quantity": 10,
      "unit_price": 200000.00,
      "total": 2000000.00
    }
  ],
  "subtotal": 2000000.00,
  "tax": 150000.00,
  "shipping_cost": 50000.00,
  "total_amount": 2200000.00,
  "payment_method": "credit",
  "payment_terms": "net_30",
  "notes": "Urgent delivery required"
}
```

**Response**:
```json
{
  "id": "uuid",
  "order_number": "PO-20251013-ABC12345",
  "due_date": "2025-11-12T10:00:00",
  "created_at": "2025-10-13T10:00:00",
  "message": "Purchase order created successfully"
}
```

#### GET `/api/inventory/purchase-orders`
Get purchase orders

**Query Parameters**:
- `agent_id` (optional)
- `manufacturer_id` (optional)
- `status` (optional): pending, approved, processing, shipped, delivered, cancelled

#### PUT `/api/inventory/purchase-orders/{order_id}/status`
Update purchase order status

**Request Body**:
```json
{
  "status": "approved"
}
```

---

### Credit Facility Endpoints

#### POST `/api/inventory/credit/apply`
Apply for credit facility

**Request Body**:
```json
{
  "agent_id": "uuid",
  "requested_amount": 5000000.00,
  "purpose": "Inventory purchase for retail operations",
  "business_revenue": 10000000.00,
  "years_in_business": 3,
  "existing_loans": 1000000.00,
  "collateral": "Business assets and inventory",
  "guarantor_info": {
    "name": "Jane Doe",
    "phone": "+234-800-999-8888",
    "relationship": "Business Partner"
  }
}
```

**Response**:
```json
{
  "id": "uuid",
  "credit_score": 720,
  "approved_limit": 5000000.00,
  "interest_rate": 12.0,
  "status": "pending",
  "message": "Credit application submitted for review"
}
```

#### GET `/api/inventory/credit/{agent_id}`
Get credit facility details

**Response**:
```json
{
  "facility": {
    "id": "uuid",
    "agent_id": "uuid",
    "credit_limit": 5000000.00,
    "available_credit": 3000000.00,
    "utilized_credit": 2000000.00,
    "interest_rate": 12.0,
    "payment_terms": "net_30",
    "status": "active",
    "credit_score": 720
  },
  "recent_transactions": [...]
}
```

#### PUT `/api/inventory/credit/{facility_id}/approve`
Approve a credit facility

#### POST `/api/inventory/credit/{agent_id}/payment`
Make a credit payment

**Request Body**:
```json
{
  "amount": 500000.00,
  "reference": "PMT-20251013-XYZ789"
}
```

---

### Shipment & Logistics Endpoints

#### POST `/api/inventory/shipments`
Create a shipment manually

**Request Body**:
```json
{
  "purchase_order_id": "uuid",
  "agent_id": "uuid",
  "manufacturer_id": "uuid",
  "carrier": "DHL Express",
  "origin_address": "123 Industrial Area, Lagos",
  "destination_address": "456 Main Street, Abuja",
  "estimated_delivery": "2025-10-20T10:00:00",
  "status": "preparing",
  "current_location": "Lagos Warehouse",
  "tracking_history": []
}
```

#### GET `/api/inventory/shipments/track/{tracking_number}`
Track a shipment

**Response**:
```json
{
  "id": "uuid",
  "tracking_number": "TRK-20251013-ABC12345",
  "purchase_order_id": "uuid",
  "status": "in_transit",
  "current_location": "En route to Abuja",
  "estimated_delivery": "2025-10-20T10:00:00",
  "tracking_history": [
    {
      "timestamp": "2025-10-13T10:00:00",
      "status": "preparing",
      "location": "Lagos Warehouse",
      "description": "Shipment created"
    },
    {
      "timestamp": "2025-10-14T08:00:00",
      "status": "in_transit",
      "location": "En route to Abuja",
      "description": "Package picked up by carrier"
    }
  ]
}
```

#### PUT `/api/inventory/shipments/{shipment_id}/update`
Update shipment status

**Request Body**:
```json
{
  "status": "in_transit",
  "current_location": "Ibadan Hub"
}
```

#### GET `/api/inventory/logistics-providers`
Get logistics providers

**Query Parameters**:
- `service_area` (optional): Filter by service area

#### POST `/api/inventory/logistics-providers`
Register a logistics provider

---

### Analytics Endpoints

#### GET `/api/inventory/analytics/dashboard`
Get inventory dashboard analytics

**Query Parameters**:
- `agent_id` (optional): Filter by agent

**Response**:
```json
{
  "inventory_value": 50000000.00,
  "low_stock_products": 15,
  "active_purchase_orders": 25,
  "total_credit_utilized": 10000000.00,
  "pending_shipments": 18,
  "top_manufacturers": [
    {
      "name": "ABC Manufacturing",
      "id": "uuid",
      "order_count": 45,
      "total_value": 25000000.00
    }
  ]
}
```

#### GET `/api/inventory/analytics/credit-utilization`
Get credit utilization analytics

**Response**:
```json
{
  "total_facilities": 150,
  "total_credit_limit": 500000000.00,
  "total_utilized": 300000000.00,
  "total_available": 200000000.00,
  "avg_credit_score": 680
}
```

---

## 💳 Credit Scoring System

### Credit Score Calculation

**Base Score**: 500

**Revenue Factor** (max 200 points):
- > 10M: +200 points
- > 5M: +150 points
- > 1M: +100 points
- > 500K: +50 points

**Years in Business** (max 150 points):
- 15 points per year, capped at 150

**Debt-to-Revenue Ratio** (max 150 points):
- < 20%: +150 points
- < 40%: +100 points
- < 60%: +50 points

**Total Range**: 300 - 850

### Credit Limit Determination

| Credit Score | Approval Rate |
|--------------|---------------|
| 750+ | 100% of requested |
| 650-749 | 80% of requested |
| 550-649 | 60% of requested |
| < 550 | 40% of requested |

### Interest Rates

| Credit Score | Interest Rate |
|--------------|---------------|
| 750+ | 8.5% (Excellent) |
| 650-749 | 12.0% (Good) |
| 550-649 | 15.5% (Fair) |
| < 550 | 20.0% (Poor) |

---

## 📦 Payment Terms

| Term | Days | Description |
|------|------|-------------|
| IMMEDIATE | 0 | Payment due immediately |
| NET_7 | 7 | Payment due in 7 days |
| NET_15 | 15 | Payment due in 15 days |
| NET_30 | 30 | Payment due in 30 days |
| NET_60 | 60 | Payment due in 60 days |
| NET_90 | 90 | Payment due in 90 days |

---

## 🚚 Order Status Flow

```
PENDING → APPROVED → PROCESSING → SHIPPED → DELIVERED
                ↓
            CANCELLED
```

### Status Descriptions

- **PENDING**: Order created, awaiting approval
- **APPROVED**: Order approved, ready for processing
- **PROCESSING**: Manufacturer preparing order
- **SHIPPED**: Order dispatched, in transit
- **DELIVERED**: Order delivered to agent
- **CANCELLED**: Order cancelled

---

## 📍 Shipment Status Flow

```
PREPARING → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED
                ↓
            FAILED
```

---

## 🔔 Inventory Alerts

### Alert Types

1. **LOW_STOCK**: Quantity ≤ reorder level
2. **OUT_OF_STOCK**: Quantity = 0
3. **REORDER_POINT**: Quantity reached reorder threshold

### Priority Levels

- **CRITICAL**: Out of stock (quantity = 0)
- **HIGH**: Quantity < 50% of reorder level
- **MEDIUM**: Quantity ≤ reorder level
- **LOW**: Approaching reorder level

---

## 🔄 Business Workflows

### 1. Agent Orders from Manufacturer

```
1. Agent browses manufacturer catalog
2. Agent adds products to cart
3. Agent selects payment method (credit/bank transfer/mobile money)
4. If credit: Check credit availability
5. Create purchase order
6. Deduct inventory quantities
7. If credit: Utilize credit facility
8. Create shipment automatically
9. Notify manufacturer
10. Track shipment until delivery
```

### 2. Credit Application Process

```
1. Agent submits credit application
2. System calculates credit score
3. System determines credit limit
4. System calculates interest rate
5. Application goes to pending status
6. Admin reviews and approves
7. Credit facility activated
8. Agent can use credit for purchases
```

### 3. Credit Payment Process

```
1. Agent makes payment
2. System validates payment amount
3. Update utilized credit (decrease)
4. Update available credit (increase)
5. Record transaction in history
6. Generate receipt
7. Update credit status if needed
```

### 4. Shipment Tracking

```
1. Shipment created when order is approved
2. Manufacturer prepares package
3. Logistics provider picks up
4. Real-time location updates
5. Out for delivery notification
6. Delivery confirmation
7. Update order status to delivered
```

---

## 🔗 Integration with Remittance Platform

### Connected Services

1. **E-commerce Platform** (Port 8020)
   - Product synchronization
   - Order management
   - Customer data

2. **Payment Gateway** (Port 8021)
   - Payment processing
   - Transaction tracking
   - Refund handling

3. **Security Monitoring** (Port 8022)
   - Fraud detection on large orders
   - Suspicious activity alerts

4. **Workflow Orchestration** (Port 8023)
   - Order workflow automation
   - Credit approval workflows
   - Shipment workflows

---

## 📊 Sample Use Cases

### Use Case 1: Agent Purchases Inventory on Credit

**Scenario**: Agent John needs to stock 50 smartphones for his retail shop.

1. John browses manufacturer catalog
2. Selects 50 units of "Samsung Galaxy A54" @ ₦200,000 each
3. Total: ₦10,000,000
4. Selects "Credit" as payment method with NET_30 terms
5. System checks John's credit facility:
   - Credit Limit: ₦15,000,000
   - Available: ₦12,000,000
   - Utilized: ₦3,000,000
6. Credit available ✅
7. Purchase order created: PO-20251013-XYZ123
8. Inventory deducted: 50 units
9. Credit utilized: ₦10,000,000
10. New available credit: ₦2,000,000
11. Shipment created: TRK-20251013-ABC456
12. Due date: November 12, 2025
13. John receives tracking number
14. Goods delivered in 7 days
15. John pays ₦10,000,000 on due date
16. Credit restored to ₦12,000,000

### Use Case 2: Manufacturer Onboarding

**Scenario**: ABC Electronics wants to join the platform.

1. ABC submits manufacturer application
2. Provides business registration: RC987654
3. Lists product categories: Electronics, Appliances
4. Sets minimum order value: ₦50,000
5. Sets payment terms: NET_30
6. Sets lead time: 5 days
7. Platform admin reviews application
8. Verifies business registration
9. Approves manufacturer
10. ABC can now list products
11. Agents can browse ABC's catalog
12. ABC receives orders from agents
13. ABC ships products
14. ABC receives payments

### Use Case 3: Low Stock Alert

**Scenario**: Automatic reorder notification.

1. Product "iPhone 15 Pro" has reorder level: 20 units
2. Current stock: 25 units
3. Agent places order for 10 units
4. New stock: 15 units
5. System detects: 15 ≤ 20 (reorder level)
6. Alert created: LOW_STOCK, Priority: HIGH
7. Notification sent to inventory manager
8. Manager reviews alert
9. Manager creates purchase order to manufacturer
10. Stock replenished
11. Alert marked as resolved

---

## 🔐 Security Features

1. **Credit Limit Enforcement**: Prevents over-utilization
2. **Order Validation**: Validates inventory availability
3. **Payment Verification**: Ensures payment before shipment
4. **Fraud Detection**: Monitors suspicious order patterns
5. **Access Control**: Role-based permissions
6. **Audit Trail**: Complete transaction history

---

## 📈 Performance Optimizations

1. **Redis Caching**: Manufacturer and product data
2. **Database Indexing**: On frequently queried fields
3. **Connection Pooling**: Efficient database connections
4. **Background Tasks**: Shipment creation, notifications
5. **Async Operations**: Non-blocking I/O

---

## 🚀 Deployment

### Requirements

```
Python 3.11+
PostgreSQL 14+
Redis 7+
```

### Installation

```bash
cd backend/python-services/inventory-management
pip install fastapi uvicorn asyncpg redis pydantic
python comprehensive_inventory_platform.py
```

### Environment Variables

```
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=remittance
REDIS_URL=redis://localhost:6379
PORT=8027
```

---

## 📞 Support

For issues or questions, contact the platform development team.

**Service**: Inventory Management Platform  
**Port**: 8027  
**Status**: Production-Ready ✅
