# 54agent Agent Banking - User Interfaces

This repository contains all the user interfaces for the 54agent Agent Banking platform. All UIs are built with React, Vite, TailwindCSS, and use comprehensive mock data for development and testing.

## 📁 Project Structure

```
uis/
├── admin-dashboard/          # Comprehensive admin control panel (TypeScript + React)
├── communication-dashboard/  # Multi-channel communication monitoring (React)
├── customer-portal/          # Customer-facing banking interface (React)
└── inventory-management/     # Inventory tracking and management (React)
```

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- pnpm (recommended) or npm

### Installation

Each UI can be installed and run independently:

```bash
# For Admin Dashboard
cd uis/admin-dashboard
npm install
npm run dev    # Runs on port 3001

# For Communication Dashboard
cd uis/communication-dashboard
pnpm install
pnpm dev       # Runs on default port (usually 5173)

# For Customer Portal
cd uis/customer-portal
pnpm install
pnpm dev       # Runs on default port

# For Inventory Management
cd uis/inventory-management
npm install
npm run dev    # Runs on port 3004
```

## 📊 Admin Dashboard

**Port:** 3001  
**Stack:** React 18 + TypeScript + Vite + TailwindCSS  
**Features:**

### Core Components

- **Dashboard** - Real-time metrics, transaction trends, revenue analytics
- **User Management** - Comprehensive user administration with roles and permissions
- **Transaction Management** - Monitor and manage all platform transactions
- **Reports & Analytics** - Business intelligence and performance metrics
- **Compliance Monitoring** - AML/KYC compliance tracking and reporting
- **Security Center** - Security events, active sessions, vulnerability tracking
- **System Settings** - Platform configuration and preferences
- **Notification Center** - System alerts and notifications
- **Audit Logs** - Complete audit trail of all system activities
- **Performance Monitoring** - Real-time system health and performance metrics

### Mock Data Features

- 10+ comprehensive components with realistic data
- Nigerian Naira (₦) currency formatting
- Transaction analytics and trends
- User roles: Super Admin, Manager, Agent, Auditor
- Security alerts and event tracking
- Compliance metrics and reporting
- API endpoint performance monitoring

## 💬 Communication Dashboard

**Features:**

- Multi-channel messaging (WhatsApp, SMS, USSD)
- Provider monitoring (Africa's Talking, Twilio, Meta WhatsApp)
- Circuit breaker status tracking
- Delivery rate analytics
- Cost tracking and metrics
- Real-time message statistics

### Mock Data

- Hourly message statistics
- Provider-wise metrics
- Channel distribution analytics
- Delivery rate tracking

## 👤 Customer Portal

**Features:**

- Personal dashboard with account overview
- Account balance tracking (Available & Savings)
- Recent transaction history
- Quick actions (Send Money, Pay Bills, Buy Airtime, Scan QR)
- Responsive design for mobile and desktop

### Mock Data

- Account balances in Nigerian Naira
- Recent transactions with credit/debit tracking
- User authentication flow

## 📦 Inventory Management

**Port:** 3004  
**Features:**

### Inventory Management

- Complete item tracking with SKU
- Category management (Hardware, Accessories, Consumables)
- Location tracking (multiple warehouses)
- Stock level monitoring with automatic alerts
- Supplier information

### Analytics

- Stock movement charts (Inbound/Outbound)
- Category distribution visualization
- Value tracking and reporting

### Alert System

- Low stock warnings
- Critical stock alerts
- Out of stock notifications
- Automatic reorder suggestions

### Mock Data

- 10+ inventory items with realistic data
- Multiple categories and locations
- Stock status tracking (in_stock, low_stock, critical, out_of_stock)
- Price and quantity management

## 🎨 Design System

All UIs use a consistent design system:

### Colors

- Primary: Blue (#3B82F6)
- Success: Green (#10B981)
- Warning: Yellow (#F59E0B)
- Error: Red (#EF4444)
- Purple: (#8B5CF6)

### Components

- Tailwind CSS for styling
- Lucide React for icons
- Recharts for data visualization
- Shadcn/ui components (communication-dashboard, customer-portal)
- Radix UI components (admin-dashboard)

## 📱 Responsive Design

All interfaces are fully responsive and work seamlessly on:

- Desktop (1920px+)
- Laptop (1366px - 1920px)
- Tablet (768px - 1365px)
- Mobile (320px - 767px)

## 🔐 Mock Authentication

Each UI includes mock authentication:

- Customer Portal: Simple login flow
- Admin Dashboard: Role-based access
- All dashboards: Token-based session management

## 📊 Mock Data Structure

All mock data is realistic and production-ready:

- Nigerian banking context
- Naira (₦) currency
- Nigerian locations (Lagos, Abuja, Port Harcourt, Kano, Ibadan)
- Realistic transaction volumes and amounts
- Proper date/time formatting

## 🛠️ Development

### Building for Production

```bash
# Admin Dashboard
cd uis/admin-dashboard
npm run build

# Communication Dashboard
cd uis/communication-dashboard
pnpm build

# Customer Portal
cd uis/customer-portal
pnpm build

# Inventory Management
cd uis/inventory-management
npm run build
```

### Tech Stack

- **Framework:** React 18
- **Build Tool:** Vite 4
- **Language:** JavaScript/TypeScript
- **Styling:** TailwindCSS 3
- **Icons:** Lucide React
- **Charts:** Recharts 2
- **Routing:** React Router DOM 6

## 📝 Features Summary

| Feature         | Admin | Communication | Customer | Inventory |
| --------------- | ----- | ------------- | -------- | --------- |
| Dashboard       | ✅    | ✅            | ✅       | ✅        |
| Analytics       | ✅    | ✅            | ❌       | ✅        |
| User Management | ✅    | ❌            | ❌       | ❌        |
| Transactions    | ✅    | ❌            | ✅       | ❌        |
| Reports         | ✅    | ❌            | ❌       | ✅        |
| Compliance      | ✅    | ❌            | ❌       | ❌        |
| Security        | ✅    | ❌            | ❌       | ❌        |
| Inventory       | ❌    | ❌            | ❌       | ✅        |
| Alerts          | ✅    | ❌            | ❌       | ✅        |

## 🚀 Next Steps

To connect to real APIs:

1. Update the mock data imports with actual API calls
2. Configure environment variables in `.env` files
3. Implement proper error handling
4. Add authentication tokens
5. Update endpoints to match backend services

## 📄 License

Copyright © 2024 54agent Agent Banking Platform

---

Built with ❤️ for the 54agent Agent Banking Platform
