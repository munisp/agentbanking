/**
 * Real-time Status Component
 * Displays connection status and recent notifications
 * Example integration of real-time services
 */

import React, { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import {
    Badge,
    Button,
    Card,
    IconButton,
    Modal,
    Portal,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useRealtime } from "../hooks/useRealtime";
import { formatCurrency } from "../utils/formatters";
export default function RealtimeStatusWidget() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const {
    isConnected,
    isLocationTracking,
    lastTransaction,
    geofenceViolation,
    currentLocation,
    clearTransaction,
    clearGeofenceViolation,
  } = useRealtime();

  const [showTransactionModal, setShowTransactionModal] = useState(false);
  const [showViolationSnackbar, setShowViolationSnackbar] = useState(false);

  // Handle new transaction
  useEffect(() => {
    if (lastTransaction) {
      setShowTransactionModal(true);
    }
  }, [lastTransaction]);

  // Handle geofence violation
  useEffect(() => {
    if (geofenceViolation) {
      setShowViolationSnackbar(true);
    }
  }, [geofenceViolation]);

  return (
    <View>
      {/* Status Card */}
      <Card style={styles.statusCard}>
        <Card.Content>
          <View style={styles.statusRow}>
            <View style={styles.statusItem}>
              <Icon
                name={isConnected ? "wifi" : "wifi-off"}
                size={20}
                color={isConnected ? "#10B981" : "#EF4444"}
              />
              <Text style={styles.statusLabel}>
                {isConnected ? "Connected" : "Offline"}
              </Text>
            </View>

            <View style={styles.statusItem}>
              <Icon
                name={
                  isLocationTracking ? "map-marker-check" : "map-marker-off"
                }
                size={20}
                color={isLocationTracking ? "#10B981" : "#9CA3AF"}
              />
              <Text style={styles.statusLabel}>
                {isLocationTracking ? "Tracking" : "Not Tracking"}
              </Text>
            </View>

            {currentLocation && (
              <View style={styles.statusItem}>
                <Icon name="crosshairs-gps" size={20} color={colors.primary} />
                <Text style={styles.statusLabel}>
                  GPS: ±{currentLocation.accuracy?.toFixed(0)}m
                </Text>
              </View>
            )}
          </View>

          {/* Location Tracking Status - Automatic, cannot be controlled */}
          <View style={styles.statusInfo}>
            <Text style={styles.infoText}>
              📍 Location tracking is automatically enabled for security
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Transaction Modal */}
      <Portal>
        <Modal
          visible={showTransactionModal}
          onDismiss={() => {
            setShowTransactionModal(false);
            clearTransaction();
          }}
          contentContainerStyle={styles.modal}
        >
          <View style={styles.modalHeader}>
            <Icon name="cash-multiple" size={48} color="#10B981" />
            <Text style={styles.modalTitle}>Money Received!</Text>
          </View>

          {lastTransaction && (
            <View style={styles.transactionDetails}>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Amount</Text>
                <Text style={styles.detailValue}>
                  {formatCurrency(lastTransaction.amount)}
                </Text>
              </View>

              {lastTransaction.sender_name && (
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>From</Text>
                  <Text style={styles.detailValue}>
                    {lastTransaction.sender_name}
                  </Text>
                </View>
              )}

              {lastTransaction.account_number && (
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>Account</Text>
                  <Text style={styles.detailValue}>
                    {lastTransaction.account_number}
                  </Text>
                </View>
              )}

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Time</Text>
                <Text style={styles.detailValue}>
                  {new Date(lastTransaction.timestamp).toLocaleTimeString()}
                </Text>
              </View>
            </View>
          )}

          <Button
            mode="contained"
            onPress={() => {
              setShowTransactionModal(false);
              clearTransaction();
            }}
            style={styles.modalButton}
          >
            OK
          </Button>
        </Modal>
      </Portal>

      {/* Geofence Violation Snackbar */}
      <Snackbar
        visible={showViolationSnackbar}
        onDismiss={() => {
          setShowViolationSnackbar(false);
          clearGeofenceViolation();
        }}
        duration={5000}
        action={{
          label: "Dismiss",
          onPress: () => {
            setShowViolationSnackbar(false);
            clearGeofenceViolation();
          },
        }}
        style={styles.snackbar}
      >
        <View style={styles.snackbarContent}>
          <Icon name="alert" size={20} color="#fff" />
          <Text style={styles.snackbarText}>
            {geofenceViolation &&
              `Device moved ${geofenceViolation.distance_from_center_km?.toFixed(1)}km from allowed area`}
          </Text>
        </View>
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  statusCard: {
    marginVertical: 8,
    marginHorizontal: 16,
  },
  statusRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: 16,
  },
  statusItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusLabel: {
    fontSize: 12,
    color: "#6B7280",
  },
  statusInfo: {
    marginTop: 12,
    paddingHorizontal: 8,
    paddingVertical: 8,
    backgroundColor: "#F0F9FF",
    borderLeftWidth: 3,
    borderLeftColor: "#0EA5E9",
    borderRadius: 4,
  },
  infoText: {
    fontSize: 12,
    color: "#0369A1",
    fontWeight: "500",
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: 8,
  },
  button: {
    minWidth: 200,
  },
  modal: {
    backgroundColor: "white",
    padding: 24,
    margin: 20,
    borderRadius: 16,
  },
  modalHeader: {
    alignItems: "center",
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: "bold",
    marginTop: 12,
    color: "#10B981",
  },
  transactionDetails: {
    marginVertical: 16,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  detailLabel: {
    fontSize: 14,
    color: "#6B7280",
  },
  detailValue: {
    fontSize: 14,
    fontWeight: "600",
    color: "#111827",
  },
  modalButton: {
    marginTop: 16,
  },
  snackbar: {
    backgroundColor: "#EF4444",
  },
  snackbarContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  snackbarText: {
    color: "#fff",
    flex: 1,
  },
});
