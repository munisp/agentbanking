# Real-time Notification & Geolocation Service

## Overview

This service provides real-time communication between POS devices and the backend for:

- **Geolocation tracking** with geofencing
- **Transaction notifications** (ping when money is received)
- Support for both **WebSocket** and **MQTT** protocols

## Architecture

### Backend Service

- **Python/FastAPI** service running on port `8094`
- WebSocket endpoint: `wss://54agent.upi.dev/realtime/ws/{agent_id}`
- MQTT topics:
  - `54agent/pos/{device_id}/location` - Location updates
  - `54agent/pos/{device_id}/transaction` - Transaction pings
  - `54agent/pos/{device_id}/geofence-alert` - Geofence violations

### Frontend Services

- `locationService.js` - GPS tracking and location updates
- `realtimeService.js` - WebSocket/MQTT communication
- `useRealtime.js` - React Hook for easy integration

## Features

### 1. Geolocation Tracking

- Continuous GPS tracking (foreground & background)
- Location updates sent every 30 seconds or 50 meters
- Low battery impact using balanced accuracy

### 2. Geofencing

- Define safe zones (radius in km) for POS devices
- Automatic alerts when device moves outside allowed area
- Distance calculation from geofence center

### 3. Transaction Notifications

- Real-time ping when money is received
- Custom notification sound
- Push notification with transaction details
- In-app notification display

### 4. Connection Management

- Automatic reconnection on network failure
- Heartbeat to keep connection alive
- Fallback from WebSocket to HTTP when needed

## Setup

### Backend Setup

1. Install dependencies:

```bash
cd services/realtime-notification-service
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
# Edit .env with your settings
```

3. Run migrations (tables auto-created on startup)

4. Start service:

```bash
python main.py
# or
uvicorn main:app --reload --port 8094
```

5. Optional: Setup MQTT broker (Mosquitto):

```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto

# Start broker
mosquitto -p 1883
```

### Frontend Setup (POS App)

1. Install dependencies:

```bash
cd uis/pos-agent-app
npm install expo-location expo-av expo-notifications expo-task-manager
```

2. Add notification sound:

```bash
mkdir -p assets/sounds
# Add notification.mp3 to assets/sounds/
```

3. Configure app.json:

```json
{
  "expo": {
    "plugins": [
      [
        "expo-location",
        {
          "locationAlwaysAndWhenInUsePermission": "Allow POS app to track your location for security."
        }
      ],
      [
        "expo-notifications",
        {
          "sounds": ["./assets/sounds/notification.mp3"]
        }
      ]
    ]
  }
}
```

4. Initialize services in App.js:

```javascript
import realtimeService from "./src/services/realtimeService";
import locationService from "./src/services/locationService";

// In App.js or main screen
useEffect(() => {
  // Connect to real-time service
  realtimeService.connect();

  // Start location tracking
  locationService.startTracking();

  return () => {
    realtimeService.disconnect();
    locationService.stopTracking();
  };
}, []);
```

## Usage

### Using the React Hook

```javascript
import { useRealtime } from "./hooks/useRealtime";

function DashboardScreen() {
  const {
    isConnected,
    isLocationTracking,
    lastTransaction,
    geofenceViolation,
    currentLocation,
    startLocationTracking,
    stopLocationTracking,
  } = useRealtime();

  useEffect(() => {
    if (lastTransaction) {
      Alert.alert(
        "Money Received!",
        `₦${lastTransaction.amount.toLocaleString()} from ${lastTransaction.sender_name}`,
        [{ text: "OK", onPress: () => clearTransaction() }],
      );
    }
  }, [lastTransaction]);

  useEffect(() => {
    if (geofenceViolation) {
      Alert.alert("Location Warning", "POS device is outside allowed area", [
        { text: "OK" },
      ]);
    }
  }, [geofenceViolation]);

  return (
    <View>
      <Text>Connection: {isConnected ? "Connected" : "Disconnected"}</Text>
      <Text>
        Location Tracking: {isLocationTracking ? "Active" : "Inactive"}
      </Text>
      {currentLocation && (
        <Text>
          Location: {currentLocation.latitude.toFixed(6)},{" "}
          {currentLocation.longitude.toFixed(6)}
        </Text>
      )}
    </View>
  );
}
```

### Creating Geofences

```javascript
// Backend API call
const response = await fetch(
  "https://54agent.upi.dev/realtime/api/v1/geofence/create",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_id: "agent123",
      tenant_id: "tenant456",
      center_latitude: 6.5244,
      center_longitude: 3.3792,
      radius_km: 2.0,
      name: "Lagos Main Store",
    }),
  },
);
```

### Sending Transaction Notifications

```javascript
// Called by ledger/account service when transaction completes
const response = await fetch(
  "https://54agent.upi.dev/realtime/api/v1/transaction/notify",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": "tenant456",
    },
    body: JSON.stringify({
      transaction_id: "TXN123456",
      agent_id: "agent123",
      tenant_id: "tenant456",
      amount: 5000.0,
      transaction_type: "credit",
      sender_name: "John Doe",
      account_number: "1234567890",
    }),
  },
);
```

## API Endpoints

### WebSocket

- `wss://54agent.upi.dev/realtime/ws/{agent_id}?device_id={device_id}`

### HTTP Endpoints

- `POST /api/v1/location/update` - Update location (fallback)
- `POST /api/v1/transaction/notify` - Send transaction ping
- `POST /api/v1/geofence/create` - Create geofence
- `GET /api/v1/geofence/list/{agent_id}` - List geofences
- `GET /api/v1/location/history/{device_id}` - Get location history

### MQTT Topics

- Publish: `54agent/pos/{device_id}/location`
- Subscribe: `54agent/pos/{device_id}/transaction`
- Subscribe: `54agent/pos/{device_id}/geofence-alert`

## Database Tables

```sql
-- POS device location history
CREATE TABLE pos_device_locations (
  id UUID PRIMARY KEY,
  device_id VARCHAR(100),
  agent_id VARCHAR(100),
  tenant_id VARCHAR(100),
  latitude FLOAT,
  longitude FLOAT,
  accuracy FLOAT,
  timestamp TIMESTAMP,
  is_within_geofence BOOLEAN,
  speed FLOAT,
  battery_level INTEGER
);

-- Geofence definitions
CREATE TABLE pos_geofences (
  id UUID PRIMARY KEY,
  agent_id VARCHAR(100),
  tenant_id VARCHAR(100),
  center_latitude FLOAT,
  center_longitude FLOAT,
  radius_km FLOAT,
  name VARCHAR(255),
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Transaction notifications
CREATE TABLE transaction_notifications (
  id UUID PRIMARY KEY,
  transaction_id VARCHAR(100),
  agent_id VARCHAR(100),
  tenant_id VARCHAR(100),
  device_id VARCHAR(100),
  amount FLOAT,
  transaction_type VARCHAR(50),
  sender_name VARCHAR(255),
  account_number VARCHAR(50),
  notification_sent_at TIMESTAMP,
  was_delivered BOOLEAN,
  delivered_at TIMESTAMP
);
```

## Production Considerations

1. **MQTT Broker**: Use managed MQTT service (AWS IoT Core, HiveMQ Cloud)
2. **SSL/TLS**: Enable wss:// and mqtts://
3. **Authentication**: Add JWT token validation
4. **Rate Limiting**: Prevent location spam
5. **Data Retention**: Archive old location data
6. **Monitoring**: Track connection health, message delivery
7. **Scaling**: Use Redis for connection state if multiple service instances

## License

MIT
