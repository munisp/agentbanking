import { Audio } from "expo-av";
import * as SecureStore from "expo-secure-store";
import { accountApi, authHeaders, networkOperationsApi } from "./apiService";

const BASE_URL = "https://54agent.upi.dev";
const DEFAULT_TENANT_ID = "bpmgd";
// WebSocket URL for realtime-notification-service (via APISIX gateway)
const NOTIFICATION_WS_URL = "wss://54agent.upi.dev/realtime/ws";

class NotificationService {
  constructor() {
    this.ws = null;
    this.reconnectTimeout = null;
    this.reconnectDelay = 3000; // 3 seconds
    this.maxReconnectDelay = 30000; // 30 seconds
    this.maxRetries = 5;
    this.retryCount = 0;
    this.permanentlyDisabled = false; // set true when endpoint is confirmed unavailable
    this.listeners = [];
    this.isConnected = false;
    this.agentId = null;
    this.sound = null;
    this.shouldConnect = false;
    this.processedMessages = new Set(); // Track processed message IDs to prevent duplicates
    this.maxProcessedMessages = 1000; // Limit set size to prevent memory issues
  }

  /**
   * Initialize WebSocket connection for real-time notifications
   * @param {string} agentId - The agent's keycloak ID
   */
  async connect(agentId) {
    if (!agentId) return;

    // Endpoint confirmed unavailable — never attempt again for this session
    if (this.permanentlyDisabled) return;

    // Already connected with the same agent — no-op
    if (this.isConnected && this.agentId === agentId) return;

    this.agentId = agentId;
    this.shouldConnect = true;

    // Close existing connection if any
    if (this.ws) {
      this.ws.close();
    }

    try {
      const wsUrl = `${NOTIFICATION_WS_URL}/${agentId}`;
      console.log(`Connecting to notification service: ${wsUrl}`);

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("✅ Connected to notification service");
        this.isConnected = true;
        this.reconnectDelay = 3000; // Reset delay on successful connection
        this.retryCount = 0; // Reset retry count on success

        // Send ping every 30 seconds to keep connection alive
        this.startPingInterval();
      };

      this.ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log("📨 Notification received:", message);

          // Skip duplicate messages based on message_id
          if (message.message_id) {
            if (this.processedMessages.has(message.message_id)) {
              console.log(
                `⏭️  Skipping duplicate notification: ${message.message_id}`,
              );
              return;
            }

            // Add to processed set
            this.processedMessages.add(message.message_id);

            // Limit set size to prevent memory issues
            if (this.processedMessages.size > this.maxProcessedMessages) {
              // Remove oldest entries (convert to array, slice, convert back)
              const entries = Array.from(this.processedMessages);
              this.processedMessages = new Set(
                entries.slice(-this.maxProcessedMessages / 2),
              );
            }
          }

          // Handle different message types
          switch (message.type) {
            case "transaction_ping":
              await this.handleTransactionPing(message);
              break;
            case "geofence_violation":
              await this.handleGeofenceViolation(message);
              break;
            case "pong":
              // Keep-alive response
              break;
            default:
              console.log("Unknown message type:", message.type);
          }

          // Notify all listeners
          this.notifyListeners(message);
        } catch (error) {
          console.error("Error processing notification:", error);
        }
      };

      this.ws.onerror = () => {
        // Downgraded to warn — WS being unavailable is not a fatal app error
        if (!this.permanentlyDisabled) {
          console.warn(`⚠️ Notification service unavailable (attempt ${this.retryCount + 1}/${this.maxRetries})`);
        }
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this.stopPingInterval();

        if (!this.shouldConnect) return;

        if (this.retryCount >= this.maxRetries) {
          console.warn("Notification service disabled after max retries — will not reconnect.");
          this.shouldConnect = false;
          this.permanentlyDisabled = true;
          return;
        }

        // Close code 1006 = abnormal/refused — endpoint likely doesn't exist
        if (event?.code === 1006 && this.retryCount >= 2) {
          console.warn("Notification WebSocket repeatedly refused — disabling.");
          this.shouldConnect = false;
          this.permanentlyDisabled = true;
          return;
        }

        this.scheduleReconnect();
      };
    } catch (error) {
      console.error("Error connecting to notification service:", error);
      if (this.shouldConnect) {
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    console.log(`Reconnecting in ${this.reconnectDelay / 1000} seconds...`);

    this.reconnectTimeout = setTimeout(() => {
      if (this.shouldConnect && this.agentId) {
        this.retryCount += 1;
        this.connect(this.agentId);
        // Increase delay for next attempt (exponential backoff)
        this.reconnectDelay = Math.min(
          this.reconnectDelay * 1.5,
          this.maxReconnectDelay,
        );
      }
    }, this.reconnectDelay);
  }

  /**
   * Start sending periodic pings
   */
  startPingInterval() {
    this.pingInterval = setInterval(() => {
      if (
        this.isConnected &&
        this.ws &&
        this.ws.readyState === WebSocket.OPEN
      ) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop sending pings
   */
  stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Handle incoming transaction notification
   */
  async handleTransactionPing(message) {
    const { payload } = message;

    console.log(
      `💰 Transaction received: ${payload.amount} NGN from ${payload.sender_name}`,
    );

    // Play notification sound/beep
    await this.playNotificationSound();

    // Send acknowledgment
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "ack",
          message_id: message.message_id,
        }),
      );
    }

    // You can add additional logic here:
    // - Show in-app notification
    // - Update transaction list
    // - Trigger haptic feedback
  }

  /**
   * Handle geofence violation alert
   */
  async handleGeofenceViolation(message) {
    const { payload } = message;
    console.warn(
      `⚠️ Geofence violation: ${payload.distance_from_center_km}km from center`,
    );

    // Play warning sound
    await this.playNotificationSound("warning");
  }

  /**
   * Play notification sound (beep)
   */
  async playNotificationSound(type = "transaction") {
    try {
      // Unload previous sound if any
      if (this.sound) {
        await this.sound.unloadAsync();
      }

      // Load and play sound based on type
      // You'll need to add sound files to your assets folder
      const soundFile =
        type === "warning"
          ? require("../../assets/sounds/warning.mp3")
          : require("../../assets/sounds/notification.mp3");

      const { sound } = await Audio.Sound.createAsync(soundFile);
      this.sound = sound;

      await sound.playAsync();

      // Auto-unload after playing
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.didJustFinish) {
          sound.unloadAsync();
        }
      });
    } catch (error) {
      console.error("Error playing notification sound:", error);
      // Fallback: Use system beep or vibration
      // You can add Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success) here
    }
  }

  /**
   * Add a listener for notifications
   * @param {function} callback - Function to call when notification is received
   * @returns {function} Unsubscribe function
   */
  addListener(callback) {
    this.listeners.push(callback);

    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter((l) => l !== callback);
    };
  }

  /**
   * Notify all listeners of new message
   */
  notifyListeners(message) {
    this.listeners.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        console.error("Error in notification listener:", error);
      }
    });
  }

  /**
   * Send location update (if needed for geofencing)
   */
  async sendLocationUpdate(location) {
    if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      const agentDetails = await this.getAgentDetails();

      const locationUpdate = {
        type: "location_update",
        payload: {
          device_id: agentDetails.device_id || "mobile-app",
          agent_id: this.agentId,
          tenant_id: agentDetails.tenant_id || DEFAULT_TENANT_ID,
          latitude: location.latitude,
          longitude: location.longitude,
          accuracy: location.accuracy,
          speed: location.speed || null,
          battery_level: null, // Can be obtained from device
        },
      };

      this.ws.send(JSON.stringify(locationUpdate));
    }
  }

  /**
   * Get agent details from secure storage
   */
  async getAgentDetails() {
    try {
      const tenantId = await SecureStore.getItemAsync("tenantId");
      const deviceId = await SecureStore.getItemAsync("deviceId");

      return {
        tenant_id: tenantId || DEFAULT_TENANT_ID,
        device_id: deviceId,
      };
    } catch (error) {
      console.error("Error getting agent details:", error);
      return {
        tenant_id: DEFAULT_TENANT_ID,
        device_id: null,
      };
    }
  }

  /**
   * Disconnect from notification service
   */
  disconnect() {
    this.shouldConnect = false;
    this.isConnected = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    this.stopPingInterval();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    // Clear processed messages on explicit disconnect
    this.processedMessages.clear();

    console.log("Disconnected from notification service");
  }

  /**
   * Get connection status
   */
  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      agentId: this.agentId,
    };
  }
}

// Export singleton instance
export default new NotificationService();
