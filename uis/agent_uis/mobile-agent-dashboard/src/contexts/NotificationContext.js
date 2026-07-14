import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";
import { StyleSheet } from "react-native";
import { Snackbar, useTheme} from "react-native-paper";
import notificationService from "../services/notificationService";

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

  const [notifications, setNotifications] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [agentId, setAgentId] = useState(null);
  const [processedTransactions, setProcessedTransactions] = useState(new Set());
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarType, setSnackbarType] = useState("info");
  const locationSubscriptionRef = useRef(null);

  // Initialize notification service on mount
  useEffect(() => {
    let checkConnection = null;
    let unsubscribe = () => {};

    const startLocationTracking = async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== "granted") {
          return;
        }

        locationSubscriptionRef.current = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.Balanced,
            timeInterval: 10000,
            distanceInterval: 20,
          },
          (location) => {
            notificationService.sendLocationUpdate(location.coords);
          },
        );
      } catch (error) {
        console.error("Error starting location tracking:", error);
      }
    };

    const initializeNotifications = async () => {
      try {
        // Get agent ID from secure storage
        const storedAgentId = await SecureStore.getItemAsync("keycloakId");

        if (storedAgentId) {
          setAgentId(storedAgentId);

          // Connect to notification service
          await notificationService.connect(storedAgentId);

          // Monitor connection status
          checkConnection = setInterval(() => {
            const status = notificationService.getConnectionStatus();
            setIsConnected(status.isConnected);
          }, 5000);

          // Add listener for incoming notifications
          unsubscribe = notificationService.addListener(
            handleIncomingNotification,
          );

          await startLocationTracking();
        }
      } catch (error) {
        console.error("Error initializing notifications:", error);
      }
    };

    initializeNotifications();

    return () => {
      if (checkConnection) {
        clearInterval(checkConnection);
      }

      unsubscribe();

      if (locationSubscriptionRef.current) {
        locationSubscriptionRef.current.remove();
        locationSubscriptionRef.current = null;
      }

      notificationService.disconnect();
    };
  }, []);

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

  return (
    <NotificationContext.Provider value={value}>
      {children}
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
  snackbar: {
    marginBottom: 60,
  },
  snackbarSuccess: {
    backgroundColor: "#10B981",
  },
  snackbarInfo: {
    backgroundColor: "#3B82F6",
  },
});

export default NotificationContext;
