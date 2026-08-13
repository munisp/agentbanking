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
import { spacing, theme } from "../../theme";
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
  const [prevTransactions, setPrevTransactions] = useState(null); // null = growth unavailable

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

      let hasRealData = false;

      // Try to fetch real transactions for the period
      try {
        const txnResponse = await networkOperationsApi.listTransactions({
          agent_id: agentId,
          ...dateFilter,
          page: 1,
          limit: 1000,
        });
        const txnData = txnResponse.transactions || txnResponse.data || [];
        if (txnData.length > 0) {
          setTransactions(txnData);
          hasRealData = true;
        }
      } catch (err) {
        console.log("Transactions fetch error:", err.message);
      }

      // Try to fetch real commissions for the period
      try {
        const commResponse = await commissionApi.listCommissions(agentId, {
          ...dateFilter,
          page: 1,
          limit: 1000,
        });
        const commData = commResponse.commissions || commResponse.data || [];
        if (commData.length > 0) {
          setCommissions(commData);
          hasRealData = true;
        }
      } catch (err) {
        console.log("Commissions fetch error:", err.message);
      }

      // Fetch the previous equivalent period so the growth rate is computed
      // from real data (never a hard-coded percentage).
      if (hasRealData) {
        try {
          const prevFilter = getPreviousDateFilter(period);
          const prevResponse = await networkOperationsApi.listTransactions({
            agent_id: agentId,
            ...prevFilter,
            page: 1,
            limit: 1000,
          });
          setPrevTransactions(prevResponse.transactions || prevResponse.data || []);
        } catch (err) {
          console.log("Previous-period fetch error:", err.message);
          setPrevTransactions(null);
        }
      } else {
        // No fabricated fallback: when the server has no data (or is
        // unreachable) the screen shows an honest empty/error state.
        setTransactions([]);
        setCommissions([]);
        setPrevTransactions(null);
      }
    } catch (err) {
      console.error("Projection data fetch error:", err);
      setTransactions([]);
      setCommissions([]);
      setError("Could not load projection data: " + (err.message || "API unavailable"));
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

  // The equivalent period immediately preceding the current one.
  const getPreviousDateFilter = (period) => {
    const end = new Date();
    let windowDays;
    switch (period) {
      case "week":
        windowDays = 7;
        break;
      case "quarter":
        windowDays = 90;
        break;
      case "month":
      default:
        windowDays = 30;
    }
    const prevEnd = new Date(end.getTime() - windowDays * 24 * 60 * 60 * 1000);
    const prevStart = new Date(prevEnd.getTime() - windowDays * 24 * 60 * 60 * 1000);
    return {
      start_date: prevStart.toISOString(),
      end_date: prevEnd.toISOString(),
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
        acc.creditCount += 1;
      } else {
        acc.debitVolume += amount;
        acc.debitCount += 1;
      }

      // Count by type
      const type = txn.type || "other";
      acc.byType[type] = (acc.byType[type] || 0) + 1;
      acc.volumeByType[type] = (acc.volumeByType[type] || 0) + amount;

      return acc;
    },
    {
      totalVolume: 0,
      creditVolume: 0,
      debitVolume: 0,
      transactionCount: 0,
      creditCount: 0,
      debitCount: 0,
      byType: {},
      volumeByType: {},
    },
  );

  const commissionMetrics = commissions.reduce(
    (acc, comm) => {
      const amount = parseFloat(comm.amount || comm.commission_amount || 0);
      acc.totalCommission += amount;
      acc.commissionCount += 1;
      acc.maxCommission = Math.max(acc.maxCommission, amount);
      acc.minCommission = Math.min(acc.minCommission, amount);
      return acc;
    },
    {
      totalCommission: 0,
      commissionCount: 0,
      maxCommission: 0,
      minCommission: Infinity,
    },
  );

  // Calculate averages
  const avgTransactionValue =
    metrics.transactionCount > 0
      ? metrics.totalVolume / metrics.transactionCount
      : 0;
  const avgDailyVolume = metrics.totalVolume / getDaysInPeriod(period);
  const avgDailyCommission =
    commissionMetrics.totalCommission / getDaysInPeriod(period);
  const avgCommissionPerTransaction =
    metrics.transactionCount > 0
      ? commissionMetrics.totalCommission / metrics.transactionCount
      : 0;

  // Project next period
  const projectedVolume = avgDailyVolume * getDaysInPeriod(period);
  const projectedCommission = avgDailyCommission * getDaysInPeriod(period);
  const projectedTransactions =
    (metrics.transactionCount / getDaysInPeriod(period)) *
    getDaysInPeriod(period);

  // Growth rate computed from the real previous-period volume fetched from
  // the backend. When previous-period data is unavailable, growth is reported
  // as unavailable — never a hard-coded percentage.
  const previousVolume = prevTransactions
    ? prevTransactions.reduce((acc, txn) => acc + (parseFloat(txn.amount || 0) || 0), 0)
    : null;
  const growthRate =
    previousVolume != null && previousVolume > 0
      ? ((metrics.totalVolume - previousVolume) / previousVolume) * 100
      : null;
  const projectedGrowthVolume =
    growthRate != null ? projectedVolume * (1 + growthRate / 100) : null;

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
              <Icon name="trending-up" size={20} color={theme.colors.success} />
              <Text variant="bodySmall" style={styles.indicatorText}>
                Credit: ₦{metrics.creditVolume.toLocaleString()} (
                {metrics.creditCount})
              </Text>
            </View>
            <View style={styles.indicator}>
              <Icon name="trending-down" size={20} color={theme.colors.error} />
              <Text variant="bodySmall" style={styles.indicatorText}>
                Debit: ₦{metrics.debitVolume.toLocaleString()} (
                {metrics.debitCount})
              </Text>
            </View>
          </View>

          <View style={styles.growthCard}>
            <View style={styles.growthItem}>
              <Icon
                name="chart-timeline-variant"
                size={24}
                color={theme.colors.primary}
              />
              <Text variant="bodySmall" style={styles.growthLabel}>
                Projected Growth Rate
              </Text>
              <Text
                variant="titleLarge"
                style={[
                  styles.growthValue,
                  { color: growthRate != null && growthRate < 0 ? "#B00020" : theme.colors.success },
                ]}
              >
                {growthRate != null
                  ? `${growthRate >= 0 ? "+" : ""}${growthRate.toFixed(1)}%`
                  : "Unavailable"}
              </Text>
            </View>
            <View style={styles.growthItem}>
              <Icon name="cash-plus" size={24} color={theme.colors.accent} />
              <Text variant="bodySmall" style={styles.growthLabel}>
                With Growth Volume
              </Text>
              <Text variant="titleLarge" style={styles.growthValue}>
                {projectedGrowthVolume != null
                  ? `₦${projectedGrowthVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                  : "Unavailable"}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Transaction Breakdown by Type */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Transaction Breakdown
          </Text>

          {Object.entries(metrics.byType).map(([type, count]) => {
            const percentage = (count / metrics.transactionCount) * 100;
            const volume = metrics.volumeByType[type] || 0;
            return (
              <View key={type} style={styles.breakdownRow}>
                <View style={styles.breakdownLeft}>
                  <Icon
                    name={
                      type === "deposit"
                        ? "cash-plus"
                        : type === "withdrawal"
                          ? "cash-minus"
                          : type === "transfer"
                            ? "bank-transfer"
                            : type === "purchase"
                              ? "cart"
                              : "swap-horizontal"
                    }
                    size={20}
                    color={theme.colors.primary}
                  />
                  <View style={styles.breakdownInfo}>
                    <Text variant="bodyMedium" style={styles.breakdownType}>
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </Text>
                    <Text variant="bodySmall" style={styles.breakdownStats}>
                      {count} txns · ₦{volume.toLocaleString()}
                    </Text>
                  </View>
                </View>
                <Chip
                  mode="flat"
                  compact
                  style={styles.percentageChip}
                  textStyle={styles.percentageText}
                >
                  {percentage.toFixed(1)}%
                </Chip>
              </View>
            );
          })}
        </Card.Content>
      </Card>

      {/* Commission Details */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Commission Analytics
          </Text>

          <View style={styles.commissionGrid}>
            <View style={styles.commissionItem}>
              <Icon name="cash-check" size={20} color={theme.colors.success} />
              <Text variant="bodySmall" style={styles.commissionLabel}>
                Avg per Transaction
              </Text>
              <Text variant="titleMedium" style={styles.commissionValue}>
                ₦
                {avgCommissionPerTransaction.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
            </View>

            <View style={styles.commissionItem}>
              <Icon
                name="arrow-up-bold"
                size={20}
                color={theme.colors.accent}
              />
              <Text variant="bodySmall" style={styles.commissionLabel}>
                Highest Earned
              </Text>
              <Text variant="titleMedium" style={styles.commissionValue}>
                ₦
                {commissionMetrics.maxCommission.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
            </View>

            <View style={styles.commissionItem}>
              <Icon
                name="arrow-down-bold"
                size={20}
                color={theme.colors.textSecondary}
              />
              <Text variant="bodySmall" style={styles.commissionLabel}>
                Lowest Earned
              </Text>
              <Text variant="titleMedium" style={styles.commissionValue}>
                ₦
                {(commissionMetrics.minCommission === Infinity
                  ? 0
                  : commissionMetrics.minCommission
                ).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </View>

            <View style={styles.commissionItem}>
              <Icon name="chart-box" size={20} color={theme.colors.primary} />
              <Text variant="bodySmall" style={styles.commissionLabel}>
                Projected Txns
              </Text>
              <Text variant="titleMedium" style={styles.commissionValue}>
                {Math.round(projectedTransactions)}
              </Text>
            </View>
          </View>

          <Text variant="bodySmall" style={styles.disclaimerText}>
            * Commission rates may vary based on transaction type and volume
          </Text>
        </Card.Content>
      </Card>

      {/* Performance Summary */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Performance Summary
          </Text>

          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Icon
                name="calendar-clock"
                size={24}
                color={theme.colors.primary}
              />
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Period Duration
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                {getDaysInPeriod(period)} days
              </Text>
            </View>

            <View style={styles.summaryItem}>
              <Icon name="chart-line" size={24} color={theme.colors.success} />
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Daily Avg Volume
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                ₦
                {avgDailyVolume.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
            </View>
          </View>

          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Icon
                name="cash-multiple"
                size={24}
                color={theme.colors.accent}
              />
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Daily Avg Commission
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                ₦
                {avgDailyCommission.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </Text>
            </View>

            <View style={styles.summaryItem}>
              <Icon name="percent" size={24} color={theme.colors.primary} />
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Commission Rate
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                {(
                  (commissionMetrics.totalCommission / metrics.totalVolume) *
                  100
                ).toFixed(2)}
                %
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
  growthCard: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  growthItem: {
    flex: 1,
    backgroundColor: "#F0FDF4",
    padding: spacing.md,
    borderRadius: 8,
    alignItems: "center",
  },
  growthLabel: {
    color: theme.colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
  },
  growthValue: {
    fontWeight: "bold",
    color: theme.colors.primary,
    marginTop: spacing.xs,
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  breakdownLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
  },
  breakdownInfo: {
    flex: 1,
  },
  breakdownType: {
    fontWeight: "600",
    marginBottom: 2,
  },
  breakdownStats: {
    color: theme.colors.textSecondary,
    fontSize: 12,
  },
  percentageChip: {
    backgroundColor: theme.colors.primary + "20",
    height: 24,
  },
  percentageText: {
    fontSize: 11,
    fontWeight: "600",
    color: theme.colors.primary,
  },
  commissionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  commissionItem: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
    alignItems: "center",
  },
  commissionLabel: {
    color: theme.colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
  },
  commissionValue: {
    fontWeight: "bold",
    color: theme.colors.text,
    marginTop: spacing.xs,
  },
  summaryRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  summaryItem: {
    flex: 1,
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
    alignItems: "center",
  },
  summaryLabel: {
    color: theme.colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
  },
  summaryValue: {
    fontWeight: "bold",
    color: theme.colors.text,
    marginTop: spacing.xs,
  },
  disclaimerText: {
    color: "#9CA3AF",
    fontStyle: "italic",
    textAlign: "center",
    marginTop: spacing.xs,
  },
});
