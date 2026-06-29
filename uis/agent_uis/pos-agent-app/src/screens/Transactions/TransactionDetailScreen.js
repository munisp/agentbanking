import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, View } from "react-native";
import {
    ActivityIndicator,
    Button,
    Card,
    Divider,
    Text, useTheme} from "react-native-paper";
import { agentApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { printTransactionReceipt } from "../../utils/receiptPrinter";

export default function TransactionDetailScreen({
 route }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { transaction } = route.params;
  const [agentData, setAgentData] = useState(null);
  const [printing, setPrinting] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgentData();
  }, []);

  const fetchAgentData = async () => {
    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        setLoading(false);
        return;
      }

      const res = await agentApi.getAgentByKeycloakId(keycloakId);
      setAgentData(res.agent || res);
    } catch (err) {
      console.error("Failed to fetch agent data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handlePrintReceipt = async () => {
    try {
      setPrinting(true);

      await printTransactionReceipt(transaction, {
        storeName: agentData?.business_name || "Area Konnect by Fidelity Agent",
        agentName:
          agentData?.full_name ||
          agentData?.first_name + " " + agentData?.last_name,
        agentPhone: agentData?.phone_number,
        agentId: agentData?.agent_id,
        storeAddress: agentData?.address,
      });

      Alert.alert("Success", "Receipt printed successfully!");
    } catch (err) {
      console.error("Print error:", err);
      Alert.alert("Print Error", err.message || "Failed to print receipt");
    } finally {
      setPrinting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.statusContainer}>
            <Text variant="headlineSmall" style={styles.amount}>
              ₦{transaction.amount.toLocaleString()}
            </Text>
            <Text variant="bodyMedium" style={styles.status}>
              {transaction.status.toUpperCase()}
            </Text>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Transaction ID
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {transaction.id}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Recipient
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {transaction.recipient}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Type
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {transaction.type.replace("_", " ")}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Date & Time
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {new Date(transaction.date).toLocaleString()}
            </Text>
          </View>
        </Card.Content>
      </Card>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" />
          <Text variant="bodySmall" style={styles.loadingText}>
            Loading agent info...
          </Text>
        </View>
      ) : (
        <View style={styles.actions}>
          <Button
            mode="contained"
            icon="printer"
            onPress={handlePrintReceipt}
            loading={printing}
            disabled={printing}
            style={styles.actionButton}
          >
            {printing ? "Printing..." : "Print Receipt"}
          </Button>
          <Button mode="outlined" style={styles.actionButton}>
            Share
          </Button>
          <Button mode="outlined" style={styles.actionButton}>
            Report Issue
          </Button>
        </View>
      )}
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
  },
  card: {
    marginTop: spacing.md,
  },
  statusContainer: {
    alignItems: "center",
    paddingVertical: spacing.lg,
  },
  amount: {
    fontWeight: "bold",
    marginBottom: spacing.sm,
  },
  status: {
    color: "#10B981",
    fontWeight: "600",
  },
  divider: {
    marginVertical: spacing.lg,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
  },
  label: {
    color: "#6B7280",
  },
  value: {
    fontWeight: "600",
  },
  actions: {
    marginTop: spacing.lg,
    marginBottom: spacing.xl,
  },
  actionButton: {
    marginBottom: spacing.md,
  },
  loadingContainer: {
    marginTop: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
  },
  loadingText: {
    marginTop: spacing.sm,
    color: "#6B7280",
  },
});
