import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Chip, Divider, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing, theme } from "../../theme";
export default function POSDetailsScreen({
 route }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { terminal } = route.params;

  // Mock analytics data
  const analyticsData = {
    today: {
      transactions: 47,
      volume: 125000,
      successRate: 94.5,
      avgTransactionValue: 2659,
    },
    week: {
      transactions: 312,
      volume: 847000,
      successRate: 92.8,
      avgTransactionValue: 2714,
    },
    month: {
      transactions: 1245,
      volume: 3250000,
      successRate: 93.2,
      avgTransactionValue: 2610,
    },
    hourlyTrend: [
      { hour: "06:00", txns: 2, volume: 5000 },
      { hour: "08:00", txns: 5, volume: 12500 },
      { hour: "10:00", txns: 8, volume: 25000 },
      { hour: "12:00", txns: 12, volume: 35000 },
      { hour: "14:00", txns: 9, volume: 22000 },
      { hour: "16:00", txns: 7, volume: 18000 },
      { hour: "18:00", txns: 4, volume: 7500 },
    ],
    transactionsByType: [
      { type: "purchase", count: 28, percentage: 59.6, avgAmount: 3200 },
      { type: "withdrawal", count: 12, percentage: 25.5, avgAmount: 5000 },
      { type: "balance_inquiry", count: 5, percentage: 10.6, avgAmount: 0 },
      { type: "transfer", count: 2, percentage: 4.3, avgAmount: 15000 },
    ],
    performance: {
      uptime: 99.5,
      avgResponseTime: 1.8,
      failedTransactions: 3,
      networkStrength: 85,
    },
  };

  const recentTransactions = [
    {
      id: "1",
      amount: 5000,
      type: "purchase",
      time: "10:30 AM",
      status: "success",
      card: "****4532",
    },
    {
      id: "2",
      amount: 3500,
      type: "purchase",
      time: "09:15 AM",
      status: "success",
      card: "****7821",
    },
    {
      id: "3",
      amount: 12000,
      type: "withdrawal",
      time: "08:45 AM",
      status: "success",
      card: "****2341",
    },
    {
      id: "4",
      amount: 2500,
      type: "purchase",
      time: "08:20 AM",
      status: "failed",
      card: "****9012",
    },
    {
      id: "5",
      amount: 8500,
      type: "transfer",
      time: "07:55 AM",
      status: "success",
      card: "****6734",
    },
  ];

  const getSuccessColor = (rate) => {
    if (rate >= 90) return theme.colors.success;
    if (rate >= 75) return theme.colors.warning;
    return theme.colors.error;
  };

  return (
    <ScrollView style={styles.container}>
      {/* Terminal Info Card */}
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

      {/* Analytics Overview */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Icon name="chart-line" size={24} color={theme.colors.primary} />
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Analytics Overview
            </Text>
          </View>

          <View style={styles.analyticsGrid}>
            <View style={styles.analyticsItem}>
              <Icon
                name="swap-horizontal"
                size={20}
                color={theme.colors.primary}
              />
              <Text variant="headlineMedium" style={styles.analyticsValue}>
                {analyticsData.today.transactions}
              </Text>
              <Text variant="bodySmall" style={styles.analyticsLabel}>
                Transactions Today
              </Text>
            </View>

            <View style={styles.analyticsItem}>
              <Icon
                name="cash-multiple"
                size={20}
                color={theme.colors.success}
              />
              <Text variant="headlineMedium" style={styles.analyticsValue}>
                ₦{(analyticsData.today.volume / 1000).toFixed(0)}K
              </Text>
              <Text variant="bodySmall" style={styles.analyticsLabel}>
                Volume Today
              </Text>
            </View>

            <View style={styles.analyticsItem}>
              <Icon
                name="check-circle"
                size={20}
                color={getSuccessColor(analyticsData.today.successRate)}
              />
              <Text
                variant="headlineMedium"
                style={[
                  styles.analyticsValue,
                  { color: getSuccessColor(analyticsData.today.successRate) },
                ]}
              >
                {analyticsData.today.successRate}%
              </Text>
              <Text variant="bodySmall" style={styles.analyticsLabel}>
                Success Rate
              </Text>
            </View>

            <View style={styles.analyticsItem}>
              <Icon name="calculator" size={20} color={theme.colors.accent} />
              <Text variant="headlineMedium" style={styles.analyticsValue}>
                ₦{(analyticsData.today.avgTransactionValue / 1000).toFixed(1)}K
              </Text>
              <Text variant="bodySmall" style={styles.analyticsLabel}>
                Avg. Transaction
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Performance Metrics */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Icon name="speedometer" size={24} color={theme.colors.primary} />
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Performance Metrics
            </Text>
          </View>

          <View style={styles.metricRow}>
            <View style={styles.metricItem}>
              <View style={styles.metricHeader}>
                <Icon
                  name="cloud-check"
                  size={18}
                  color={theme.colors.success}
                />
                <Text variant="bodySmall" style={styles.metricLabel}>
                  Uptime
                </Text>
              </View>
              <Text variant="titleLarge" style={styles.metricValue}>
                {analyticsData.performance.uptime}%
              </Text>
            </View>

            <View style={styles.metricItem}>
              <View style={styles.metricHeader}>
                <Icon
                  name="speedometer-medium"
                  size={18}
                  color={theme.colors.warning}
                />
                <Text variant="bodySmall" style={styles.metricLabel}>
                  Response Time
                </Text>
              </View>
              <Text variant="titleLarge" style={styles.metricValue}>
                {analyticsData.performance.avgResponseTime}s
              </Text>
            </View>
          </View>

          <View style={styles.metricRow}>
            <View style={styles.metricItem}>
              <View style={styles.metricHeader}>
                <Icon name="signal" size={18} color={theme.colors.primary} />
                <Text variant="bodySmall" style={styles.metricLabel}>
                  Network
                </Text>
              </View>
              <Text variant="titleLarge" style={styles.metricValue}>
                {analyticsData.performance.networkStrength}%
              </Text>
            </View>

            <View style={styles.metricItem}>
              <View style={styles.metricHeader}>
                <Icon
                  name="alert-circle"
                  size={18}
                  color={theme.colors.error}
                />
                <Text variant="bodySmall" style={styles.metricLabel}>
                  Failed Today
                </Text>
              </View>
              <Text variant="titleLarge" style={styles.metricValue}>
                {analyticsData.performance.failedTransactions}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Transactions by Type */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Icon name="chart-donut" size={24} color={theme.colors.primary} />
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Transactions by Type
            </Text>
          </View>

          {analyticsData.transactionsByType.map((item, index) => (
            <View key={index} style={styles.typeRow}>
              <View style={styles.typeInfo}>
                <Text variant="bodyMedium" style={styles.typeName}>
                  {item.type
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (l) => l.toUpperCase())}
                </Text>
                <Text variant="bodySmall" style={styles.typeDetails}>
                  {item.count} txns · Avg: ₦{item.avgAmount.toLocaleString()}
                </Text>
              </View>
              <Text variant="titleMedium" style={styles.typePercentage}>
                {item.percentage.toFixed(1)}%
              </Text>
            </View>
          ))}
        </Card.Content>
      </Card>

      {/* Hourly Trend */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Icon name="chart-bar" size={24} color={theme.colors.primary} />
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Hourly Trend (Today)
            </Text>
          </View>

          <View style={styles.trendContainer}>
            {analyticsData.hourlyTrend.map((item, index) => (
              <View key={index} style={styles.trendItem}>
                <View
                  style={[
                    styles.trendBar,
                    {
                      height: (item.txns / 12) * 80,
                      backgroundColor: theme.colors.primary,
                    },
                  ]}
                />
                <Text variant="bodySmall" style={styles.trendLabel}>
                  {item.hour}
                </Text>
                <Text variant="bodySmall" style={styles.trendCount}>
                  {item.txns}
                </Text>
              </View>
            ))}
          </View>
        </Card.Content>
      </Card>

      {/* Recent Transactions */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Icon name="history" size={24} color={theme.colors.primary} />
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Recent Transactions
            </Text>
          </View>

          {recentTransactions.map((txn) => (
            <View key={txn.id} style={styles.transactionRow}>
              <View style={styles.transactionLeft}>
                <View style={styles.transactionHeader}>
                  <Text variant="bodyMedium" style={styles.transactionType}>
                    {txn.type
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                  </Text>
                  <Chip
                    mode="flat"
                    compact
                    style={[
                      styles.statusMiniChip,
                      {
                        backgroundColor:
                          txn.status === "success"
                            ? theme.colors.success + "20"
                            : theme.colors.error + "20",
                      },
                    ]}
                    textStyle={{
                      color:
                        txn.status === "success"
                          ? theme.colors.success
                          : theme.colors.error,
                      fontSize: 10,
                    }}
                  >
                    {txn.status}
                  </Chip>
                </View>
                <Text variant="bodySmall" style={styles.transactionTime}>
                  {txn.time} · Card {txn.card}
                </Text>
              </View>
              <Text
                variant="bodyLarge"
                style={[
                  styles.transactionAmount,
                  {
                    color:
                      txn.status === "success"
                        ? theme.colors.text
                        : theme.colors.textSecondary,
                  },
                ]}
              >
                ₦{txn.amount.toLocaleString()}
              </Text>
            </View>
          ))}
        </Card.Content>
      </Card>

      {/* Action Buttons */}
      <View style={styles.actions}>
        <Button mode="contained" style={styles.actionButton}>
          View All Transactions
        </Button>
        <Button mode="outlined" style={styles.actionButton}>
          Edit Location
        </Button>
        <Button
          mode="outlined"
          style={styles.actionButton}
          textColor={theme.colors.error}
        >
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
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  sectionTitle: {
    fontWeight: "bold",
  },
  analyticsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  analyticsItem: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
    alignItems: "center",
    gap: spacing.xs,
  },
  analyticsValue: {
    fontWeight: "bold",
    color: theme.colors.primary,
  },
  analyticsLabel: {
    color: theme.colors.textSecondary,
    textAlign: "center",
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  metricItem: {
    flex: 1,
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
  },
  metricHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  metricLabel: {
    color: theme.colors.textSecondary,
    fontSize: 11,
  },
  metricValue: {
    fontWeight: "bold",
    color: theme.colors.text,
  },
  typeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  typeInfo: {
    flex: 1,
  },
  typeName: {
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  typeDetails: {
    color: theme.colors.textSecondary,
    fontSize: 12,
  },
  typePercentage: {
    fontWeight: "bold",
    color: theme.colors.primary,
  },
  trendContainer: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "flex-end",
    height: 120,
    paddingVertical: spacing.md,
  },
  trendItem: {
    alignItems: "center",
    gap: spacing.xs,
  },
  trendBar: {
    width: 24,
    backgroundColor: theme.colors.primary,
    borderRadius: 4,
    minHeight: 10,
  },
  trendLabel: {
    color: theme.colors.textSecondary,
    fontSize: 10,
  },
  trendCount: {
    color: theme.colors.text,
    fontSize: 11,
    fontWeight: "600",
  },
  transactionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  transactionLeft: {
    flex: 1,
  },
  transactionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  transactionType: {
    fontWeight: "600",
  },
  statusMiniChip: {
    height: 20,
  },
  transactionTime: {
    color: "#6B7280",
  },
  transactionAmount: {
    fontWeight: "600",
    marginLeft: spacing.md,
  },
  actions: {
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  actionButton: {
    marginBottom: spacing.md,
  },
});
