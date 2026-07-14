import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Chip, Divider, Text, useTheme} from "react-native-paper";
import { spacing } from "../../theme";
export default function POSDetailsScreen({
 route }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { terminal } = route.params;

  const recentTransactions = [
    { id: "1", amount: 5000, type: "purchase", time: "10:30 AM" },
    { id: "2", amount: 3500, type: "purchase", time: "09:15 AM" },
    { id: "3", amount: 12000, type: "purchase", time: "08:45 AM" },
  ];

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.header}>
            <Text variant="headlineSmall" style={styles.serialNumber}>
              {terminal.serialNumber}
            </Text>
            <Chip
              mode="flat"
              style={[
                styles.statusChip,
                {
                  backgroundColor:
                    terminal.status === "active" ? "#10B98120" : "#6B728020",
                },
              ]}
              textStyle={{
                color: terminal.status === "active" ? "#10B981" : "#6B7280",
              }}
            >
              {terminal.status}
            </Chip>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Location
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {terminal.location}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text variant="bodyMedium" style={styles.label}>
              Last Transaction
            </Text>
            <Text variant="bodyMedium" style={styles.value}>
              {new Date(terminal.lastTransaction).toLocaleString()}
            </Text>
          </View>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Today's Summary
          </Text>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryValue}>
                47
              </Text>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Transactions
              </Text>
            </View>
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryValue}>
                ₦125K
              </Text>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Volume
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Recent Transactions
          </Text>
          {recentTransactions.map((txn) => (
            <View key={txn.id} style={styles.transactionRow}>
              <View>
                <Text variant="bodyMedium" style={styles.transactionType}>
                  {txn.type}
                </Text>
                <Text variant="bodySmall" style={styles.transactionTime}>
                  {txn.time}
                </Text>
              </View>
              <Text variant="bodyLarge" style={styles.transactionAmount}>
                ₦{txn.amount.toLocaleString()}
              </Text>
            </View>
          ))}
        </Card.Content>
      </Card>

      <View style={styles.actions}>
        <Button mode="contained" style={styles.actionButton}>
          View All Transactions
        </Button>
        <Button mode="outlined" style={styles.actionButton}>
          Edit Location
        </Button>
        <Button mode="outlined" style={styles.actionButton} textColor="#EF4444">
          Deactivate Terminal
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
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  serialNumber: {
    fontWeight: "bold",
  },
  statusChip: {
    height: 28,
  },
  divider: {
    marginVertical: spacing.md,
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
  sectionTitle: {
    fontWeight: "bold",
    marginBottom: spacing.md,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-around",
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
  transactionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  transactionType: {
    textTransform: "capitalize",
  },
  transactionTime: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  transactionAmount: {
    fontWeight: "600",
  },
  actions: {
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  actionButton: {
    marginBottom: spacing.md,
  },
});
