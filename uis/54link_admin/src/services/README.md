# API Services

This directory contains centralized API services for the application.

## Structure

- `api.ts` - Main axios instance with interceptors for authentication and error handling
- `auth/` - Authentication services
  - `authService.ts` - Core authentication service with login/logout
  - `useAuth.ts` - React hook for authentication state management
  - `index.ts` - Exports

## Usage

### Basic API Call

```typescript
import apiClient from '@/services/api';

// GET request
const data = await apiClient.get('/api/endpoint');

// POST request
const result = await apiClient.post('/api/endpoint', { data });
```

### Using Auth Service

```typescript
import { useAuth } from '@/services/auth';

function MyComponent() {
  const { user, isAuthenticated, login, logout, isLoading } = useAuth();
  
  // Login
  await login('user@example.com', 'password');
  
  // Logout
  logout();
}
```

### Creating a New Service

```typescript
import apiClient from '../api';

export const myService = {
  async getData() {
    return apiClient.get('/api/my-endpoint');
  },
  
  async createData(payload: any) {
    return apiClient.post('/api/my-endpoint', payload);
  }
};
```

## Features

- Automatic token injection from localStorage
- Automatic error handling and redirects
- Centralized base URL configuration
- TypeScript support
- Request/Response interceptors










