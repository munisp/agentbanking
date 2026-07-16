/**
 * Real-time Service (WebSocket/MQTT)
 * Handles real-time communication with backend
 * Receives transaction pings and geofence alerts
 */

import * as Notifications from "expo-notifications";
import * as SecureStore from "expo-secure-store";

const WEBSOCKET_URL = "wss://54agent.upi.dev/realtime/ws";
const RECONNECT_INTERVAL = 5000; // 5 seconds
const HEARTBEAT_INTERVAL = 30000; // 30 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

class RealtimeService {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.messageHandlers = {};
    this.agentId = null;
    this.deviceId = null;
  }

  /**
   * Initialize and connect
   */
  async connect() {
    try {
      this.agentId = await SecureStore.getItemAsync("agentId");
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      this.agentId = this.agentId || keycloakId;

      this.deviceId = await this.getDeviceId();

      if (!this.agentId) {
        throw new Error("Agent ID not found");
      }

      const url = `${WEBSOCKET_URL}/${this.agentId}?device_id=${this.deviceId}`;
      console.log("Connecting to WebSocket:", url);

      this.ws = new WebSocket(url);

      this.ws.onopen = () => this.handleOpen();
      this.ws.onmessage = (event) => this.handleMessage(event);
      this.ws.onerror = (error) => this.handleError(error);
      this.ws.onclose = () => this.handleClose();
    } catch (error) {
      console.error("Error connecting to WebSocket:", error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect
   */
  disconnect() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
    console.log("Disconnected from WebSocket");
  }

  /**
   * Handle connection open
   */
  handleOpen() {
    console.log("WebSocket connected");
    this.isConnected = true;
    this.reconnectAttempts = 0;

    // Start heartbeat
    this.startHeartbeat();

    // Notify listeners
    this.emit("connected");
  }

  /**
   * Handle incoming message
   */
  async handleMessage(event) {
    try {
      const data = JSON.parse(event.data);
      const messageType = data.type;

      console.log("WebSocket message:", messageType, data);

      switch (messageType) {
        case "transaction_ping":
          await this.handleTransactionPing(data.payload);
          break;

        case "geofence_violation":
          await this.handleGeofenceViolation(data.payload);
          break;

        case "sim_failover":
          await this.handleSimFailover(data.payload);
          break;

        case "pong":
          // Heartbeat response
          break;

        default:
          console.log("Unknown message type:", messageType);
      }

      // Call registered handlers
      if (this.messageHandlers[messageType]) {
        this.messageHandlers[messageType].forEach((handler) =>
          handler(data.payload),
        );
      }

      // Send acknowledgment
      if (data.message_id) {
        this.sendAck(data.message_id);
      }
    } catch (error) {
      console.error("Error handling message:", error);
    }
  }

  /**
   * Handle connection error
   */
  handleError(error) {
    console.error("WebSocket error:", error);
    this.isConnected = false;
  }

  /**
   * Handle connection close
   */
  handleClose() {
    console.log("WebSocket closed");
    this.isConnected = false;

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    // Attempt reconnect
    this.scheduleReconnect();

    // Notify listeners
    this.emit("disconnected");
  }

  /**
   * Schedule reconnection
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error("Max reconnect attempts reached");
      this.emit("reconnect_failed");
      return;
    }

    this.reconnectAttempts++;
    const delay = RECONNECT_INTERVAL * this.reconnectAttempts;

    console.log(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`,
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Start heartbeat
   */
  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.sendMessage({ type: "ping" });
      }
    }, HEARTBEAT_INTERVAL);
  }

  /**
   * Send message
   */
  sendMessage(message) {
    if (this.ws && this.isConnected) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("WebSocket not connected, cannot send message");
    }
  }

  /**
   * Send acknowledgment
   */
  sendAck(messageId) {
    this.sendMessage({
      type: "ack",
      message_id: messageId,
    });
  }

  /**
   * Handle transaction ping
   */
  async handleTransactionPing(payload) {
    console.log("Transaction received:", payload);

    // Show push notification
    await this.showPushNotification({
      title: "💰 Money Received!",
      body: `₦${payload.amount.toLocaleString()} from ${payload.sender_name || "Customer"}`,
      data: payload,
    });

    // Show in-app notification
    this.emit("transaction_received", payload);
  }

  /**
   * Handle geofence violation
   */
  async handleGeofenceViolation(payload) {
    console.log("Geofence violation:", payload);

    // Show alert notification
    await this.showPushNotification({
      title: "⚠️ Location Alert",
      body: `POS device moved ${payload.distance_from_center_km.toFixed(1)}km from allowed area`,
      data: payload,
    });

    // Notify listeners
    this.emit("geofence_violation", payload);
  }


  /**
   * Handle SIM failover notification pushed by the platform after the
   * sim-orchestrator daemon reports an emergency carrier switch.
   *
   * Expected payload:
   *   { from_slot, to_slot, from_carrier, to_carrier, reason, latency_ms, loss_x10, tx_ref }
   */
  async handleSimFailover(payload) {
    console.log("SIM failover:", payload);

    const fromCarrier = payload?.from_carrier || `Slot ${payload?.from_slot ?? "?"}`;
    const toCarrier   = payload?.to_carrier   || `Slot ${payload?.to_slot   ?? "?"}`;
    const reason      = payload?.reason === "high_latency" ? "high latency" : "packet loss";

    await this.showPushNotification({
      title: "Network Switched",
      body: `Switched from ${fromCarrier} to ${toCarrier} due to ${reason}`,
      data: payload,
    });

    this.emit("sim_failover", payload);
  }

  /**
   * Show push notification
   */
  async showPushNotification(notification) {
    try {
      const { status } = await Notifications.getPermissionsAsync();

      if (status !== "granted") {
        console.log("Notification permission not granted");
        return;
      }

      await Notifications.scheduleNotificationAsync({
        content: {
          title: notification.title,
          body: notification.body,
          data: notification.data,
          sound: true,
        },
        trigger: null, // Show immediately
      });
    } catch (error) {
      console.error("Error showing push notification:", error);
    }
  }

  /**
   * Register message handler
   */
  on(messageType, handler) {
    if (!this.messageHandlers[messageType]) {
      this.messageHandlers[messageType] = [];
    }
    this.messageHandlers[messageType].push(handler);
  }

  /**
   * Unregister message handler
   */
  off(messageType, handler) {
    if (this.messageHandlers[messageType]) {
      this.messageHandlers[messageType] = this.messageHandlers[
        messageType
      ].filter((h) => h !== handler);
    }
  }

  /**
   * Emit event to all handlers
   */
  emit(event, data) {
    if (this.messageHandlers[event]) {
      this.messageHandlers[event].forEach((handler) => handler(data));
    }
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.isConnected;
  }

  /**
   * Get device ID
   */
  async getDeviceId() {
    let deviceId = await SecureStore.getItemAsync("deviceId");
    if (!deviceId) {
      deviceId = `POS-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      await SecureStore.setItemAsync("deviceId", deviceId);
    }
    return deviceId;
  }
}

// Configure notifications
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export default new RealtimeService();
