import React from "react";
import { useTheme } from 'react-native-paper';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNotifications } from "../../contexts/NotificationContext";

/**
 * Example: Add notification badge to Dashboard
 * This component can be imported in DashboardScreen.js
 */
export default function NotificationBadge({
 onPress }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
    const { unreadCount, isConnected } = useNotifications();

    return (
        <TouchableOpacity style={styles.container} onPress={onPress}>
            <View style={styles.iconContainer}>
                <Text style={styles.icon}>🔔</Text>
                {unreadCount > 0 && (
                    <View style={styles.badge}>
                        <Text style={styles.badgeText}>
                            {unreadCount > 9 ? "9+" : unreadCount}
                        </Text>
                    </View>
                )}
            </View>
            
            <View style={[
                styles.statusDot,
                isConnected ? styles.connected : styles.disconnected
            ]} />
        </TouchableOpacity>
    );
}

const makeStyles = (colors) => StyleSheet.create({
    container: {
        position: "relative",
        padding: 8,
    },
    iconContainer: {
        position: "relative",
    },
    icon: {
        fontSize: 24,
    },
    badge: {
        position: "absolute",
        top: -4,
        right: -4,
        backgroundColor: "#f44336",
        borderRadius: 10,
        minWidth: 20,
        height: 20,
        justifyContent: "center",
        alignItems: "center",
        paddingHorizontal: 4,
    },
    badgeText: {
        color: "#fff",
        fontSize: 10,
        fontWeight: "bold",
    },
    statusDot: {
        position: "absolute",
        bottom: 8,
        right: 8,
        width: 8,
        height: 8,
        borderRadius: 4,
        borderWidth: 1,
        borderColor: "#fff",
    },
    connected: {
        backgroundColor: "#4caf50",
    },
    disconnected: {
        backgroundColor: "#f44336",
    },
});
