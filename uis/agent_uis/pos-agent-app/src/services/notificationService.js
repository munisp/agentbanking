import * as SecureStore from "expo-secure-store";
import { beep } from "../lib/sunmi";
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
    this.permanentlyDisabled = false;
    this.listeners = [];
    this.isConnected = false;
    this.agentId = null;
    this.shouldConnect = false;
    this.processedMessages = new Set(); // Track processed message IDs to prevent duplicates
    this.maxProcessedMessages = 1000; // Limit set size to prevent memory issues
    this.processedTransactions = new Set(); // Track processed transaction IDs for deduplication
    this.cleanupInterval = null;
  }

  /**
   * Initialize WebSocket connection for real-time notifications
   * @param {string} agentId - The agent's keycloak ID
   */
  async connect(agentId) {
    if (!agentId) return;
    if (this.permanentlyDisabled) return;
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

        // Send ping every 30 seconds to keep connection alive
        this.startPingInterval();
        this.startCleanupInterval();
      };

      this.ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log("📨 Notification received:", message);

          // Skip duplicate messages based on message_id
          if (message.message_id) {
            if (this.processedMessages.has(message.message_id)) {
              console.log(`⏭️  Skipping duplicate notification: ${message.message_id}`);
              return;
            }
            
            // Add to processed set
            this.processedMessages.add(message.message_id);
            
            // Limit set size to prevent memory issues
            if (this.processedMessages.size > this.maxProcessedMessages) {
              // Remove oldest entries (convert to array, slice, convert back)
              const entries = Array.from(this.processedMessages);
              this.processedMessages = new Set(entries.slice(-this.maxProcessedMessages / 2));
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
            case "apk_update_available":
              await this.handleApkUpdateAvailable(message);
              break;
            case "pong":
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
        if (!this.permanentlyDisabled) {
          console.warn(`⚠️ Notification service unavailable (attempt ${this.retryCount + 1}/${this.maxRetries})`);
        }
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this.stopPingInterval();
        this.stopCleanupInterval();

        if (!this.shouldConnect) return;

        if (this.retryCount >= this.maxRetries) {
          console.warn("Notification service disabled after max retries.");
          this.shouldConnect = false;
          this.permanentlyDisabled = true;
          return;
        }

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

    this.reconnectTimeout = setTimeout(() => {
      if (this.shouldConnect && this.agentId) {
        this.retryCount += 1;
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
        this.connect(this.agentId);
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
    const transactionId = payload?.transaction_id;

    console.log(
      `💰 Transaction received: ${payload.amount} NGN from ${payload.sender_name}`,
    );

    // Check if we've already processed this transaction
    if (transactionId && this.processedTransactions.has(transactionId)) {
      console.log(`⏭️  Skipping duplicate transaction: ${transactionId}`);
      return;
    }

    // Mark transaction as processed
    if (transactionId) {
      this.processedTransactions.add(transactionId);
    }

    // Play notification beep (POS device beep)
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
   * Play notification sound (beep) using POS device
   */
  async playNotificationSound(type = "transaction") {
    try {
      // Use nexgo beep - duration in milliseconds
      // Quick beep for transaction, longer beep for warning
      const duration = type === "warning" ? 500 : 200;
      await beep(duration);
    } catch (error) {
      console.error("Error playing notification beep:", error);
    }
  }

  /**
   * Start cleanup interval to prevent memory leaks
   */
  startCleanupInterval() {
    // Clear processed transactions every 5 minutes
    this.cleanupInterval = setInterval(() => {
      console.log("🧹 Cleaning up processed transaction IDs");
      this.processedTransactions.clear();
    }, 300000); // 5 minutes
  }

  /**
   * Stop cleanup interval
   */
  stopCleanupInterval() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
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
   * Handle APK update available notification
   */
  async handleApkUpdateAvailable(message) {
    const { payload } = message;
    console.log("📦 APK update available:", payload);

    // Persist update info so POSManagementScreen can pick it up
    try {
      await SecureStore.setItemAsync(
        "pendingApkUpdate",
        JSON.stringify({
          terminal_id: payload.terminal_id,
          model_id: payload.model_id,
          apk_variant: payload.apk_variant,
          download_url: payload.download_url,
          deployment_id: payload.deployment_id,
          message: payload.message,
          received_at: new Date().toISOString(),
        }),
      );
    } catch (err) {
      console.error("Failed to store APK update info:", err);
    }

    // Play a short beep so the agent notices
    await this.playNotificationSound("update");

    // Acknowledge receipt
    if (this.ws && this.ws.readyState === WebSocket.OPEN && message.message_id) {
      this.ws.send(JSON.stringify({ type: "ack", message_id: message.message_id }));
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
    this.stopCleanupInterval();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    // Clear processed messages on explicit disconnect
    this.processedMessages.clear();
    this.processedTransactions.clear();

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
