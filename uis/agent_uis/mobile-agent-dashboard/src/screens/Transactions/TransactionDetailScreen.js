import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Divider, Text, useTheme} from "react-native-paper";
import { spacing } from "../../theme";

export default function TransactionDetailScreen({
 route }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { transaction } = route.params;

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

      <View style={styles.actions}>
        <Button mode="outlined" style={styles.actionButton}>
          Download Receipt
        </Button>
        <Button mode="outlined" style={styles.actionButton}>
          Share
        </Button>
        <Button mode="outlined" style={styles.actionButton}>
          Report Issue
        </Button>
      </View>
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
});
