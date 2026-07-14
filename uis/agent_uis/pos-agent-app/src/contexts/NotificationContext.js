import * as Haptics from "expo-haptics";
import * as SecureStore from "expo-secure-store";
import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
} from "react";
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Snackbar, useTheme} from "react-native-paper";
import mdmDeviceService from "../services/mdmDeviceService";
import notificationService from "../services/notificationService";
import { useAuth } from "./AuthContext";

const NotificationContext = createContext({
  notifications: [],
  unreadCount: 0,
  isConnected: false,
  addNotification: () => {},
  markAsRead: () => {},
  clearNotifications: () => {},
});

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      "useNotifications must be used within NotificationProvider",
    );
  }
  return context;
};

export const NotificationProvider = ({ children }) => {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const { isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [agentId, setAgentId] = useState(null);
  const [processedTransactions, setProcessedTransactions] = useState(new Set());
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarType, setSnackbarType] = useState("info");
  const [mdmModalVisible, setMdmModalVisible] = useState(false);
  const [mdmCommands, setMdmCommands] = useState([]);

  // Initialize notification service on mount
  useEffect(() => {
    let checkConnection = null;
    let unsubscribeNotifications = null;
    let unsubscribeMdm = null;
    let isMounted = true;

    const initializeNotifications = async () => {
      try {
        if (!isAuthenticated || !isMounted) return;

        const storedAgentId = await SecureStore.getItemAsync("keycloakId");
        if (!storedAgentId || !isMounted) return;

        setAgentId(storedAgentId);

        await notificationService.connect(storedAgentId);

        checkConnection = setInterval(() => {
          const status = notificationService.getConnectionStatus();
          setIsConnected(status.isConnected);
        }, 5000);

        unsubscribeNotifications = notificationService.addListener(
          handleIncomingNotification,
        );

        unsubscribeMdm = mdmDeviceService.addListener((event) => {
          if (event?.type === "pending_commands") {
            const commands = Array.isArray(event.payload) ? event.payload : [];
            if (commands.length > 0) {
              setMdmCommands(commands.map((cmd) => ({
                id: cmd.command_id,
                type: cmd.command_type,
                status: "pending",
                result: null,
              })));
              setMdmModalVisible(true);
            }
          } else if (event?.type === "command_execution_success") {
            const cmdId = event.payload?.command?.command_id;
            setMdmCommands((prev) =>
              prev.map((c) => c.id === cmdId ? { ...c, status: "success", result: event.payload?.result } : c)
            );
          } else if (event?.type === "command_execution_failed") {
            const cmdId = event.payload?.command?.command_id;
            setMdmCommands((prev) =>
              prev.map((c) => c.id === cmdId ? { ...c, status: "failed", result: event.payload?.error } : c)
            );
          }
        });

        mdmDeviceService.start({ intervalMs: 10000 });
      } catch (error) {
        console.error("Error initializing notifications:", error);
      }
    };

    initializeNotifications();

    return () => {
      isMounted = false;
      if (checkConnection) {
        clearInterval(checkConnection);
      }
      if (unsubscribeNotifications) {
        unsubscribeNotifications();
      }
      if (unsubscribeMdm) {
        unsubscribeMdm();
      }
      mdmDeviceService.stop();
      notificationService.disconnect();
    };
  }, [isAuthenticated]);

  /**
   * Handle incoming notification from WebSocket
   */
  const handleIncomingNotification = useCallback(
    (message) => {
      console.log("📬 New notification received:", message);

      // Skip keep-alive pong messages (defensive check)
      if (message.type === "pong") {
        return;
      }

      // Check for duplicate transactions
      const transactionId = message.payload?.transaction_id;
      const isNewTransaction =
        !transactionId || !processedTransactions.has(transactionId);

      // Mark transaction as processed
      if (transactionId && isNewTransaction) {
        setProcessedTransactions((prev) => new Set(prev).add(transactionId));
      }

      // Create notification object
      const notification = {
        id: message.message_id || Date.now().toString(),
        type: message.type,
        timestamp: new Date(),
        read: false,
        data: message.payload,
      };

      // Add to notifications list
      setNotifications((prev) => [notification, ...prev].slice(0, 50)); // Keep last 50

      // Only trigger haptic feedback for NEW transactions
      if (isNewTransaction) {
        try {
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        } catch (error) {
          console.error("Error triggering haptic feedback:", error);
        }
      }

      // Handle specific notification types
      if (message.type === "transaction_ping") {
        const { amount, sender_name, transaction_type } = message.payload;

        // Show pop-up notification
        const formattedAmount = new Intl.NumberFormat("en-NG", {
          style: "currency",
          currency: "NGN",
        }).format(amount);

        const notificationText = `${transaction_type.toUpperCase()}: ${formattedAmount} from ${sender_name}`;
        setSnackbarMessage(notificationText);
        setSnackbarType(transaction_type === "credit" ? "success" : "info");
        setSnackbarVisible(true);

        console.log(
          `💰 ${transaction_type.toUpperCase()}: ₦${amount} from ${sender_name}`,
        );
      }
    },
    [processedTransactions],
  );

  /**
   * Add notification manually (for testing or other sources)
   */
  const addNotification = useCallback((notification) => {
    const newNotification = {
      id: Date.now().toString(),
      timestamp: new Date(),
      read: false,
      ...notification,
    };
    setNotifications((prev) => [newNotification, ...prev].slice(0, 50));
  }, []);

  /**
   * Mark notification as read
   */
  const markAsRead = useCallback((notificationId) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n)),
    );
  }, []);

  /**
   * Clear all notifications
   */
  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  /**
   * Get unread count
   */
  const unreadCount = notifications.filter((n) => !n.read).length;

  const value = {
    notifications,
    unreadCount,
    isConnected,
    addNotification,
    markAsRead,
    clearNotifications,
  };

  const statusColor = { pending: "#F59E0B", success: "#10B981", failed: "#EF4444" };
  const statusLabel = { pending: "⏳ Pending", success: "✅ Done", failed: "❌ Failed" };
  const commandLabel = (type) => (type || "unknown").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <NotificationContext.Provider value={value}>
      {children}

      <Modal
        visible={mdmModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setMdmModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>📡 MDM Commands</Text>
            <ScrollView style={styles.commandList}>
              {mdmCommands.map((cmd) => (
                <View key={cmd.id} style={styles.commandRow}>
                  <View style={[styles.statusDot, { backgroundColor: statusColor[cmd.status] }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.commandType}>{commandLabel(cmd.type)}</Text>
                    <Text style={styles.commandStatus}>{statusLabel[cmd.status]}</Text>
                    {cmd.result ? <Text style={styles.commandResult} numberOfLines={2}>{String(cmd.result)}</Text> : null}
                  </View>
                </View>
              ))}
            </ScrollView>
            <TouchableOpacity style={styles.dismissBtn} onPress={() => setMdmModalVisible(false)}>
              <Text style={styles.dismissText}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={4000}
        style={[
          styles.snackbar,
          snackbarType === "success"
            ? styles.snackbarSuccess
            : styles.snackbarInfo,
        ]}
        action={{
          label: "Dismiss",
          onPress: () => setSnackbarVisible(false),
        }}
      >
        {snackbarMessage}
      </Snackbar>
    </NotificationContext.Provider>
  );
};

const makeStyles = (colors) => StyleSheet.create({
  snackbar: { marginBottom: 60 },
  snackbarSuccess: { backgroundColor: "#10B981" },
  snackbarInfo: { backgroundColor: "#3B82F6" },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modalCard: {
    backgroundColor: "#1E293B",
    borderRadius: 16,
    padding: 20,
    width: "100%",
    maxHeight: "70%",
  },
  modalTitle: {
    color: "#F8FAFC",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 16,
  },
  commandList: { maxHeight: 300 },
  commandRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginTop: 4,
  },
  commandType: { color: "#F8FAFC", fontSize: 15, fontWeight: "600" },
  commandStatus: { color: "#94A3B8", fontSize: 12, marginTop: 2 },
  commandResult: { color: "#64748B", fontSize: 11, marginTop: 2 },
  dismissBtn: {
    marginTop: 16,
    backgroundColor: "#3B82F6",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  dismissText: { color: "#fff", fontWeight: "700", fontSize: 15 },
});

export default NotificationContext;
