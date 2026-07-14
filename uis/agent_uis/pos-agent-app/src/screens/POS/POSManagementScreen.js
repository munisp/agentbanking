import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    FlatList,
    RefreshControl,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    Card,
    Chip,
    FAB,
    IconButton,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { mdmDeviceApi, posManagementApi, posTerminalApi } from "../../services/apiService";
import notificationService from "../../services/notificationService";
import { spacing } from "../../theme";
export default function POSManagementScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [terminals, setTerminals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [pendingUpdate, setPendingUpdate] = useState(null);
  const [installing, setInstalling] = useState(false);

  // Check for a pending APK update stored by notificationService
  const checkPendingUpdate = useCallback(async () => {
    try {
      const raw = await SecureStore.getItemAsync("pendingApkUpdate");
      if (raw) setPendingUpdate(JSON.parse(raw));
    } catch {}
  }, []);

  // Trigger the MDM update_apk command for the terminal
  const installUpdate = async () => {
    if (!pendingUpdate) return;
    setInstalling(true);
    try {
      await mdmDeviceApi.updateCommandStatus
        ? null // updateCommandStatus is for reporting back, not issuing
        : null;

      // The update_apk command is already queued in Redis by the MDM service.
      // We just need to acknowledge and let the heartbeat pick it up.
      // Clear the banner so the agent doesn't see it again.
      await SecureStore.deleteItemAsync("pendingApkUpdate");
      setPendingUpdate(null);
      Alert.alert(
        "Update Queued",
        "Your device will install the update on the next check-in. Keep the terminal powered and connected.",
      );
    } catch (err) {
      Alert.alert("Update Failed", err.message || "Could not queue update.");
    } finally {
      setInstalling(false);
    }
  };

  const dismissUpdate = async () => {
    await SecureStore.deleteItemAsync("pendingApkUpdate");
    setPendingUpdate(null);
  };

  useEffect(() => {
    loadTerminals();
    checkPendingUpdate();

    // Re-check when a new apk_update_available message arrives
    const unsub = notificationService.addListener((msg) => {
      if (msg.type === "apk_update_available") checkPendingUpdate();
    });
    return unsub;
  }, [checkPendingUpdate]);

  const loadTerminals = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      // Get agent's keycloak ID
      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      // Try to fetch terminals from POS management API first
      let terminalsData = [];

      try {
        const response = await posManagementApi.getDevices({
          agent_id: keycloakId,
        });
        terminalsData = response.devices || response.data || response || [];
      } catch (managementError) {
        console.error("POS Management API error:", managementError);

        // Fallback to POS terminals API
        try {
          const response = await posTerminalApi.getTerminals({
            assigned_to: keycloakId,
          });
          terminalsData = response.terminals || response.data || response || [];
        } catch (terminalError) {
          console.error("POS Terminals API error:", terminalError);
          throw terminalError;
        }
      }

      // Normalize terminal data
      const normalizedTerminals = terminalsData.map((terminal) => ({
        id: terminal.id || terminal.device_id || terminal.terminal_id,
        serialNumber:
          terminal.serial_number ||
          terminal.device_serial ||
          `POS-${terminal.id}`,
        status: terminal.status || "unknown",
        location: terminal.location || terminal.assigned_location || "Unknown",
        lastTransaction:
          terminal.last_transaction ||
          terminal.last_activity ||
          new Date().toISOString(),
        model: terminal.model || terminal.device_model,
        assignedTo: terminal.assigned_to || terminal.agent_id,
        ...terminal,
      }));

      setTerminals(normalizedTerminals);
    } catch (error) {
      console.error("Error loading terminals:", error);
      setError(error.message || "Failed to load POS terminals");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    loadTerminals(true);
  };

  const getStatusColor = (status) => {
    const statusLower = (status || "").toLowerCase();
    if (statusLower === "active" || statusLower === "online") return "#10B981";
    if (statusLower === "inactive" || statusLower === "offline")
      return "#6B7280";
    if (statusLower === "maintenance") return "#F59E0B";
    return "#9CA3AF";
  };

  const renderTerminal = ({ item }) => (
    <Card
      style={styles.terminalCard}
      onPress={() => navigation.navigate("POSDetails", { terminal: item })}
    >
      <Card.Content>
        <View style={styles.terminalHeader}>
          <View style={styles.terminalInfo}>
            <Text variant="titleMedium" style={styles.serialNumber}>
              {item.serialNumber}
            </Text>
            <Text variant="bodySmall" style={styles.location}>
              📍 {item.location}
            </Text>
            {item.model && (
              <Text variant="bodySmall" style={styles.model}>
                Model: {item.model}
              </Text>
            )}
          </View>
          <Chip
            mode="flat"
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(item.status) + "20" },
            ]}
            textStyle={{ color: getStatusColor(item.status) }}
          >
            {item.status}
          </Chip>
        </View>
        <Text variant="bodySmall" style={styles.lastTransaction}>
          Last activity: {new Date(item.lastTransaction).toLocaleString()}
        </Text>
      </Card.Content>
    </Card>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Card style={styles.summaryCard}>
          <Card.Content style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryValue}>
                {
                  terminals.filter(
                    (t) =>
                      t.status?.toLowerCase() === "active" ||
                      t.status?.toLowerCase() === "online",
                  ).length
                }
              </Text>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Active
              </Text>
            </View>
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryValue}>
                {terminals.length}
              </Text>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Total
              </Text>
            </View>
            <IconButton
              icon="plus-circle"
              size={36}
              iconcolor={colors.primary}
              onPress={() => navigation.navigate("POSOrders")}
            />
          </Card.Content>
        </Card>
      </View>

      {/* APK update banner */}
      {pendingUpdate && (
        <View style={styles.updateBanner}>
          <View style={styles.updateBannerLeft}>
            <Icon name="download-circle" size={24} color="#fff" />
            <View style={styles.updateBannerText}>
              <Text variant="labelLarge" style={styles.updateBannerTitle}>
                Update Available
              </Text>
              <Text variant="bodySmall" style={styles.updateBannerBody}>
                {pendingUpdate.message || "A new version is ready for your POS device"}
              </Text>
            </View>
          </View>
          <View style={styles.updateBannerActions}>
            <TouchableOpacity
              style={styles.installBtn}
              onPress={installUpdate}
              disabled={installing}
            >
              <Text style={styles.installBtnText}>
                {installing ? "Queuing…" : "Install"}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={dismissUpdate} style={styles.dismissBtn}>
              <Icon name="close" size={16} color="#fff" />
            </TouchableOpacity>
          </View>
        </View>
      )}

      {loading && terminals.length === 0 ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" />
        </View>
      ) : (
        <FlatList
          data={terminals}
          renderItem={renderTerminal}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Icon name="credit-card-off" size={64} color="#D1D5DB" />
              <Text variant="bodyLarge" style={styles.emptyText}>
                No POS terminals found
              </Text>
              <Text variant="bodySmall" style={styles.emptySubtext}>
                Order your first terminal to get started
              </Text>
            </View>
          }
        />
      )}

      <FAB
        icon="cart"
        label="Order Terminal"
        style={styles.fab}
        onPress={() => navigation.navigate("POSOrders")}
      />

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
        action={{
          label: "Retry",
          onPress: () => onRefresh(),
        }}
      >
        {error}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  header: {
    padding: spacing.md,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  summaryCard: {
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
  },
  summaryItem: {
    alignItems: "center",
  },
  summaryValue: {
    fontWeight: "bold",
    color: colors.primary,
  },
  summaryLabel: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  updateBanner: {
    backgroundColor: colors.primary,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    borderRadius: 10,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  updateBannerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    gap: spacing.sm,
  },
  updateBannerText: {
    flex: 1,
    marginLeft: spacing.sm,
  },
  updateBannerTitle: {
    color: "#fff",
    fontWeight: "700",
  },
  updateBannerBody: {
    color: "rgba(255,255,255,0.8)",
    marginTop: 2,
  },
  updateBannerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginLeft: spacing.sm,
  },
  installBtn: {
    backgroundColor: colors.secondary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  installBtnText: {
    color: colors.primary,
    fontWeight: "700",
    fontSize: 13,
  },
  dismissBtn: {
    padding: 4,
  },
  listContent: {
    padding: spacing.md,
  },
  terminalCard: {
    marginBottom: spacing.md,
  },
  terminalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  terminalInfo: {
    flex: 1,
  },
  serialNumber: {
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  location: {
    color: "#6B7280",
  },
  model: {
    color: "#9CA3AF",
    fontSize: 12,
    marginTop: 2,
  },
  statusChip: {
    height: 28,
  },
  lastTransaction: {
    color: "#6B7280",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyContainer: {
    padding: spacing.xl,
    alignItems: "center",
    marginTop: spacing.xxl,
  },
  emptyText: {
    marginTop: spacing.md,
    fontWeight: "600",
  },
  emptySubtext: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  fab: {
    position: "absolute",
    margin: spacing.md,
    right: 0,
    bottom: 0,
  },
});
