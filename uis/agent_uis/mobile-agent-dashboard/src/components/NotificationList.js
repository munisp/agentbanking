import { formatDistanceToNow } from "date-fns";
import { useTheme } from 'react-native-paper';
import React, { useEffect } from "react";
import { FlatList, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNotifications } from "../contexts/NotificationContext";

/**
 * Example component to display notifications
 * Add this to your Dashboard or a dedicated Notifications screen
 */
export default function NotificationList() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

    const { notifications, unreadCount, isConnected, markAsRead } = useNotifications();

    const renderNotification = ({ item }) => {
        const isTransaction = item.type === "transaction_ping";
        const isGeofence = item.type === "geofence_violation";

        return (
            <TouchableOpacity
                style={[
                    styles.notificationCard,
                    !item.read && styles.unreadCard,
                ]}
                onPress={() => markAsRead(item.id)}
            >
                <View style={styles.notificationHeader}>
                    <Text style={styles.notificationType}>
                        {isTransaction && "💰 Transaction"}
                        {isGeofence && "⚠️ Geofence Alert"}
                    </Text>
                    <Text style={styles.timestamp}>
                        {formatDistanceToNow(item.timestamp, { addSuffix: true })}
                    </Text>
                </View>

                {isTransaction && (
                    <View style={styles.transactionDetails}>
                        <Text style={styles.amount}>
                            ₦{item.data.amount?.toLocaleString()}
                        </Text>
                        <Text style={styles.sender}>
                            From: {item.data.sender_name || "Unknown"}
                        </Text>
                        <Text style={styles.transactionId}>
                            ID: {item.data.transaction_id}
                        </Text>
                    </View>
                )}

                {isGeofence && (
                    <View style={styles.geofenceDetails}>
                        <Text style={styles.alertText}>
                            Device outside geofence
                        </Text>
                        <Text style={styles.distance}>
                            Distance: {item.data.distance_from_center_km?.toFixed(2)} km
                        </Text>
                    </View>
                )}

                {!item.read && <View style={styles.unreadDot} />}
            </TouchableOpacity>
        );
    };

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.title}>Notifications</Text>
                <View style={styles.statusContainer}>
                    <View
                        style={[
                            styles.connectionStatus,
                            isConnected ? styles.connected : styles.disconnected,
                        ]}
                    />
                    <Text style={styles.statusText}>
                        {isConnected ? "Live" : "Offline"}
                    </Text>
                </View>
            </View>

            {unreadCount > 0 && (
                <View style={styles.unreadBanner}>
                    <Text style={styles.unreadText}>
                        {unreadCount} unread notification{unreadCount !== 1 ? "s" : ""}
                    </Text>
                </View>
            )}

            <FlatList
                data={notifications}
                renderItem={renderNotification}
                keyExtractor={(item) => item.id}
                contentContainerStyle={styles.listContainer}
                ListEmptyComponent={
                    <View style={styles.emptyContainer}>
                        <Text style={styles.emptyText}>No notifications yet</Text>
                        <Text style={styles.emptySubtext}>
                            You'll be notified when transactions occur
                        </Text>
                    </View>
                }
            />
        </View>
    );
}

const makeStyles = (colors) => StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#f5f5f5",
    },
    header: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        padding: 16,
        backgroundColor: "#fff",
        borderBottomWidth: 1,
        borderBottomColor: "#e0e0e0",
    },
    title: {
        fontSize: 24,
        fontWeight: "bold",
        color: "#333",
    },
    statusContainer: {
        flexDirection: "row",
        alignItems: "center",
    },
    connectionStatus: {
        width: 10,
        height: 10,
        borderRadius: 5,
        marginRight: 6,
    },
    connected: {
        backgroundColor: "#4caf50",
    },
    disconnected: {
        backgroundColor: "#f44336",
    },
    statusText: {
        fontSize: 12,
        color: "#666",
    },
    unreadBanner: {
        backgroundColor: "#2196f3",
        padding: 12,
        alignItems: "center",
    },
    unreadText: {
        color: "#fff",
        fontWeight: "600",
    },
    listContainer: {
        padding: 16,
    },
    notificationCard: {
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 16,
        marginBottom: 12,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
        position: "relative",
    },
    unreadCard: {
        borderLeftWidth: 4,
        borderLeftColor: "#2196f3",
    },
    notificationHeader: {
        flexDirection: "row",
        justifyContent: "space-between",
        marginBottom: 8,
    },
    notificationType: {
        fontSize: 16,
        fontWeight: "600",
        color: "#333",
    },
    timestamp: {
        fontSize: 12,
        color: "#999",
    },
    transactionDetails: {
        paddingTop: 8,
        borderTopWidth: 1,
        borderTopColor: "#f0f0f0",
    },
    amount: {
        fontSize: 24,
        fontWeight: "bold",
        color: "#4caf50",
        marginBottom: 4,
    },
    sender: {
        fontSize: 14,
        color: "#666",
        marginBottom: 2,
    },
    transactionId: {
        fontSize: 12,
        color: "#999",
        fontFamily: "monospace",
    },
    geofenceDetails: {
        paddingTop: 8,
        borderTopWidth: 1,
        borderTopColor: "#f0f0f0",
    },
    alertText: {
        fontSize: 14,
        color: "#ff9800",
        marginBottom: 4,
    },
    distance: {
        fontSize: 12,
        color: "#666",
    },
    unreadDot: {
        position: "absolute",
        top: 16,
        right: 16,
        width: 8,
        height: 8,
        borderRadius: 4,
        backgroundColor: "#2196f3",
    },
    emptyContainer: {
        alignItems: "center",
        justifyContent: "center",
        paddingVertical: 60,
    },
    emptyText: {
        fontSize: 18,
        color: "#999",
        marginBottom: 8,
    },
    emptySubtext: {
        fontSize: 14,
        color: "#bbb",
    },
});
