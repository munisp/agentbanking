import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    Dimensions,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Card,
    Chip,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { commissionApi, networkOperationsApi } from "../../services/apiService";
import { spacing } from "../../theme";
const SCREEN_WIDTH = Dimensions.get("window").width;

export default function ProjectionsScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [period, setPeriod] = useState("month");
  const [transactions, setTransactions] = useState([]);
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchProjectionData();
  }, [period]);

  const fetchProjectionData = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const agentId = await SecureStore.getItemAsync("agentId");
      const dateFilter = getDateFilter(period);

      // Fetch transactions for the period
      try {
        const txnResponse = await networkOperationsApi.listTransactions({
          agent_id: agentId,
          ...dateFilter,
          page: 1,
          limit: 1000,
        });
        setTransactions(txnResponse.transactions || txnResponse.data || []);
      } catch (err) {
        console.log("Transactions fetch error:", err.message);
      }

      // Fetch commissions for the period
      try {
        const commResponse = await commissionApi.listCommissions(agentId, {
          ...dateFilter,
          page: 1,
          limit: 1000,
        });
        setCommissions(commResponse.commissions || commResponse.data || []);
      } catch (err) {
        console.log("Commissions fetch error:", err.message);
      }
    } catch (err) {
      console.error("Projection data fetch error:", err);
      setError(err.message || "Failed to load projection data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const getDateFilter = (period) => {
    const now = new Date();
    let startDate;

    switch (period) {
      case "week":
        startDate = new Date(now.setDate(now.getDate() - 7));
        break;
      case "month":
        startDate = new Date(now.setMonth(now.getMonth() - 1));
        break;
      case "quarter":
        startDate = new Date(now.setMonth(now.getMonth() - 3));
        break;
      default:
        startDate = new Date(now.setMonth(now.getMonth() - 1));
    }

    return {
      start_date: startDate.toISOString(),
      end_date: new Date().toISOString(),
    };
  };

  const onRefresh = () => {
    fetchProjectionData(true);
  };

  // Calculate metrics
  const metrics = transactions.reduce(
    (acc, txn) => {
      const amount = parseFloat(txn.amount || 0);
      const isCredit = parseFloat(txn.credit || 0) > 0;

      acc.totalVolume += amount;
      acc.transactionCount += 1;

      if (isCredit) {
        acc.creditVolume += amount;
      } else {
        acc.debitVolume += amount;
      }

      return acc;
    },
    {
      totalVolume: 0,
      creditVolume: 0,
      debitVolume: 0,
      transactionCount: 0,
    },
  );

  const commissionMetrics = commissions.reduce(
    (acc, comm) => {
      const amount = parseFloat(comm.amount || comm.commission_amount || 0);
      acc.totalCommission += amount;
      acc.commissionCount += 1;
      return acc;
    },
    { totalCommission: 0, commissionCount: 0 },
  );

  // Calculate averages
  const avgTransactionValue =
    metrics.transactionCount > 0
      ? metrics.totalVolume / metrics.transactionCount
      : 0;
  const avgDailyVolume = metrics.totalVolume / getDaysInPeriod(period);
  const avgDailyCommission =
    commissionMetrics.totalCommission / getDaysInPeriod(period);

  // Project next period
  const projectedVolume = avgDailyVolume * getDaysInPeriod(period);
  const projectedCommission = avgDailyCommission * getDaysInPeriod(period);

  function getDaysInPeriod(period) {
    switch (period) {
      case "week":
        return 7;
      case "month":
        return 30;
      case "quarter":
        return 90;
      default:
        return 30;
    }
  }

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Period Selector */}
      <View style={styles.periodContainer}>
        <SegmentedButtons
          value={period}
          onValueChange={setPeriod}
          buttons={[
            { value: "week", label: "Week" },
            { value: "month", label: "Month" },
            { value: "quarter", label: "Quarter" },
          ]}
        />
      </View>

      {/* Current Performance */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Current Period Performance
          </Text>

          <View style={styles.metricRow}>
            <View style={styles.metricCard}>
              <Icon name="swap-horizontal" size={24} color={colors.primary} />
              <Text variant="bodySmall" style={styles.metricLabel}>
                Total Volume
              </Text>
              <Text variant="titleMedium" style={styles.metricValue}>
                ₦{metrics.totalVolume.toLocaleString()}
              </Text>
            </View>

            <View style={styles.metricCard}>
              <Icon name="counter" size={24} color="#10B981" />
              <Text variant="bodySmall" style={styles.metricLabel}>
                Transactions
              </Text>
              <Text variant="titleMedium" style={styles.metricValue}>
                {metrics.transactionCount}
              </Text>
            </View>
          </View>

          <View style={styles.metricRow}>
            <View style={styles.metricCard}>
              <Icon name="cash-multiple" size={24} color="#F59E0B" />
              <Text variant="bodySmall" style={styles.metricLabel}>
                Total Commission
              </Text>
              <Text variant="titleMedium" style={styles.metricValue}>
                ₦{commissionMetrics.totalCommission.toLocaleString()}
              </Text>
            </View>

            <View style={styles.metricCard}>
              <Icon name="calculator" size={24} color="#6B7280" />
              <Text variant="bodySmall" style={styles.metricLabel}>
                Avg Transaction
              </Text>
              <Text variant="titleMedium" style={styles.metricValue}>
                ₦
                {avgTransactionValue.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Projections for Next Period */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.projectionHeader}>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Next {period.charAt(0).toUpperCase() + period.slice(1)} Projection
            </Text>
            <Chip mode="flat" style={styles.projectionChip}>
              Estimated
            </Chip>
          </View>

          <View style={styles.projectionCard}>
            <View style={styles.projectionItem}>
              <Text variant="bodyMedium" style={styles.projectionLabel}>
                Projected Volume
              </Text>
              <Text variant="titleLarge" style={styles.projectionValue}>
                ₦
                {projectedVolume.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
              <Text variant="bodySmall" style={styles.projectionNote}>
                Based on ₦
                {avgDailyVolume.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}{" "}
                avg/day
              </Text>
            </View>
          </View>

          <View style={styles.projectionCard}>
            <View style={styles.projectionItem}>
              <Text variant="bodyMedium" style={styles.projectionLabel}>
                Projected Commission
              </Text>
              <Text
                variant="titleLarge"
                style={[styles.projectionValue, { color: "#10B981" }]}
              >
                ₦
                {projectedCommission.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
              <Text variant="bodySmall" style={styles.projectionNote}>
                Based on ₦
                {avgDailyCommission.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}{" "}
                avg/day
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Growth Indicators */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Growth Indicators
          </Text>

          <View style={styles.indicatorRow}>
            <View style={styles.indicator}>
              <Icon name="trending-up" size={20} color="#10B981" />
              <Text variant="bodySmall" style={styles.indicatorText}>
                Credit: ₦{metrics.creditVolume.toLocaleString()}
              </Text>
            </View>
            <View style={styles.indicator}>
              <Icon name="trending-down" size={20} color="#EF4444" />
              <Text variant="bodySmall" style={styles.indicatorText}>
                Debit: ₦{metrics.debitVolume.toLocaleString()}
              </Text>
            </View>
          </View>

          <Text variant="bodySmall" style={styles.disclaimerText}>
            * Projections are based on historical data and may vary based on
            market conditions
          </Text>
        </Card.Content>
      </Card>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  periodContainer: {
    padding: spacing.md,
  },
  card: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  metricCard: {
    flex: 1,
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
    alignItems: "center",
  },
  metricLabel: {
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  metricValue: {
    fontWeight: "bold",
    marginTop: spacing.xs,
  },
  projectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  projectionChip: {
    backgroundColor: "#F59E0B20",
  },
  projectionCard: {
    backgroundColor: "#EFF6FF",
    padding: spacing.md,
    borderRadius: 8,
    marginBottom: spacing.md,
  },
  projectionItem: {
    alignItems: "center",
  },
  projectionLabel: {
    color: "#6B7280",
  },
  projectionValue: {
    fontWeight: "bold",
    color: colors.primary,
    marginVertical: spacing.xs,
  },
  projectionNote: {
    color: "#9CA3AF",
    fontStyle: "italic",
  },
  indicatorRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  indicator: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#F9FAFB",
    padding: spacing.sm,
    borderRadius: 8,
  },
  indicatorText: {
    flex: 1,
  },
  disclaimerText: {
    color: "#9CA3AF",
    fontStyle: "italic",
    textAlign: "center",
  },
});
