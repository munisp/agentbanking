# Setup Instructions

## Quick Start

### 1. Backend Service

```bash
cd services/realtime-notification-service

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your database URL

# Run service
python main.py
```

### 2. POS App

```bash
cd uis/pos-agent-app

# Install new dependencies
npm install expo-location expo-av expo-notifications expo-task-manager geopy

# Add notification sound
mkdir -p assets/sounds
# Download a notification sound (MP3) and save as assets/sounds/notification.mp3
# You can use: https://notificationsounds.com/ or create your own
```

### 3. Update App Configuration

Add to `app.json`:

```json
{
  "expo": {
    "plugins": [
      [
        "expo-location",
        {
          "locationAlwaysAndWhenInUsePermission": "Allow POS app to track your location for security and geofencing."
        }
      ],
      [
        "expo-notifications",
        {
          "sounds": ["./assets/sounds/notification.mp3"]
        }
      ]
    ],
    "android": {
      "permissions": [
        "ACCESS_COARSE_LOCATION",
        "ACCESS_FINE_LOCATION",
        "ACCESS_BACKGROUND_LOCATION",
        "FOREGROUND_SERVICE",
        "FOREGROUND_SERVICE_LOCATION"
      ]
    },
    "ios": {
      "infoPlist": {
        "NSLocationAlwaysAndWhenInUseUsageDescription": "We need your location to ensure POS device stays within allowed area",
        "NSLocationWhenInUseUsageDescription": "We need your location for security",
        "UIBackgroundModes": ["location", "fetch"]
      }
    }
  }
}
```

### 4. Initialize in App

Add to your main `App.js` or `DashboardScreen`:

```javascript
import { useEffect } from 'react';
import realtimeService from './src/services/realtimeService';
import locationService from './src/services/locationService';

function App() {
  useEffect(() => {
    // Initialize services
    const initServices = async () => {
      try {
        // Connect to real-time service
        await realtimeService.connect();

        // Start location tracking
        await locationService.startTracking();

        console.log('Real-time services initialized');
      } catch (error) {
        console.error('Failed to initialize services:', error);
      }
    };

    initServices();

    // Cleanup on unmount
    return () => {
      realtimeService.disconnect();
      locationService.stopTracking();
    };
  }, []);

  return (
    // Your app content
  );
}
```

### 5. Optional: Setup MQTT Broker

If you want to use MQTT instead of WebSocket:

```bash
# Install Mosquitto (Ubuntu)
sudo apt-get update
sudo apt-get install mosquitto mosquitto-clients

# Start broker
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Test
mosquitto_pub -h localhost -t test -m "Hello MQTT"
mosquitto_sub -h localhost -t test
```

For production, use managed MQTT:

- AWS IoT Core
- HiveMQ Cloud
- CloudMQTT

### 6. Create Geofences

Use the API to create geofences:

```bash
curl -X POST https://54agent.upi.dev/realtime/api/v1/geofence/create \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "your-agent-id",
    "tenant_id": "your-tenant-id",
    "center_latitude": 6.5244,
    "center_longitude": 3.3792,
    "radius_km": 2.0,
    "name": "Main Store"
  }'
```

### 7. Integrate Transaction Webhook

In your ledger/account service, add webhook call after successful transaction:

```python
# Example: After crediting agent account
import requests

def notify_transaction(transaction):
    webhook_url = "https://54agent.upi.dev/realtime/api/v1/transaction/notify"

    payload = {
        "transaction_id": transaction.id,
        "agent_id": transaction.agent_id,
        "tenant_id": transaction.tenant_id,
        "amount": transaction.amount,
        "transaction_type": "credit",
        "sender_name": transaction.sender_name,
        "account_number": transaction.account_number,
    }

    requests.post(
        webhook_url,
        json=payload,
        headers={"x-tenant-id": transaction.tenant_id}
    )
```

### 8. Test

1. Start the backend service
2. Run the POS app
3. Check logs for connection status
4. Send a test transaction notification:

```bash
curl -X POST https://54agent.upi.dev/realtime/api/v1/transaction/notify \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: test-tenant" \
  -d '{
    "transaction_id": "TEST123",
    "agent_id": "your-agent-id",
    "tenant_id": "test-tenant",
    "amount": 5000,
    "transaction_type": "credit",
    "sender_name": "Test Customer",
    "account_number": "1234567890"
  }'
```

You should hear a notification sound and see a popup!

## Troubleshooting

### Location not working

- Check permissions in device settings
- Ensure GPS is enabled
- Check app.json configuration

### WebSocket not connecting

- Verify backend service is running
- Check firewall rules
- Try HTTP fallback first

### No notification sound

- Verify `notification.mp3` exists in `assets/sounds/`
- Check expo config includes the sound file
- Test with system notification first

### MQTT not working

- Check broker is running: `sudo systemctl status mosquitto`
- Test connection: `mosquitto_pub -h localhost -t test -m "test"`
- Check MQTT_BROKER and MQTT_PORT in .env

## Production Checklist

- [ ] Use managed MQTT broker (AWS IoT Core, HiveMQ)
- [ ] Enable SSL/TLS (wss://, mqtts://)
- [ ] Add JWT authentication
- [ ] Set up monitoring and alerts
- [ ] Configure rate limiting
- [ ] Set up log aggregation
- [ ] Archive old location data
- [ ] Load test WebSocket connections
- [ ] Test on low-bandwidth networks
- [ ] Test battery impact
