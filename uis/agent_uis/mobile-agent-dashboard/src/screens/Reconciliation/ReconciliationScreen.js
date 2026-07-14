import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    StyleSheet,
    View,
} from "react-native";
import {
    Card,
    Chip,
    Searchbar,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { networkOperationsApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function ReconciliationScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [searchQuery, setSearchQuery] = useState("");
  const [period, setPeriod] = useState("today");
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchTransactions();
  }, [period]);

  const fetchTransactions = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const agentId = await SecureStore.getItemAsync("agentId");
      const dateFilter = getDateFilter(period);

      const response = await networkOperationsApi.listTransactions({
        agent_id: agentId,
        ...dateFilter,
        page: 1,
        limit: 100,
      });
      setTransactions(response.transactions || response.data || []);
    } catch (err) {
      console.error("Transactions fetch error:", err);
      setError(err.message || "Failed to load transactions");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const getDateFilter = (period) => {
    const now = new Date();
    let startDate;

    switch (period) {
      case "today":
        startDate = new Date(now.setHours(0, 0, 0, 0));
        break;
      case "week":
        startDate = new Date(now.setDate(now.getDate() - 7));
        break;
      case "month":
        startDate = new Date(now.setMonth(now.getMonth() - 1));
        break;
      default:
        startDate = new Date(now.setHours(0, 0, 0, 0));
    }

    return {
      start_date: startDate.toISOString(),
      end_date: new Date().toISOString(),
    };
  };

  const onRefresh = () => {
    fetchTransactions(true);
  };

  const filteredTransactions = transactions.filter((txn) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      txn.reference?.toLowerCase().includes(query) ||
      txn.transaction_type?.toLowerCase().includes(query) ||
      txn.narration?.toLowerCase().includes(query)
    );
  });

  // Calculate reconciliation stats
  const stats = filteredTransactions.reduce(
    (acc, txn) => {
      const amount = parseFloat(txn.amount || 0);
      const isCredit = parseFloat(txn.credit || 0) > 0;

      acc.total += 1;
      if (isCredit) {
        acc.credit += amount;
      } else {
        acc.debit += amount;
      }

      if (
        txn.status?.toLowerCase() === "completed" ||
        txn.status?.toLowerCase() === "success"
      ) {
        acc.reconciled += 1;
      } else if (txn.status?.toLowerCase() === "pending") {
        acc.pending += 1;
      } else if (txn.status?.toLowerCase() === "failed") {
        acc.failed += 1;
      }

      return acc;
    },
    { total: 0, credit: 0, debit: 0, reconciled: 0, pending: 0, failed: 0 },
  );

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "completed" || statusLower === "success")
      return "#10B981";
    if (statusLower === "failed" || statusLower === "rejected")
      return "#EF4444";
    if (statusLower === "pending") return "#F59E0B";
    return "#6B7280";
  };

  const renderTransactionItem = ({ item }) => {
    const isCredit = parseFloat(item.credit || 0) > 0;
    const amount = parseFloat(item.amount || item.credit || item.debit || 0);

    return (
      <Card style={styles.transactionCard}>
        <Card.Content>
          <View style={styles.transactionHeader}>
            <View style={styles.transactionInfo}>
              <Text variant="titleSmall" style={styles.transactionType}>
                {item.transaction_type || "Transaction"}
              </Text>
              <Text variant="bodySmall" style={styles.transactionDate}>
                {new Date(item.created_at || item.timestamp).toLocaleString()}
              </Text>
              {item.reference && (
                <Text variant="bodySmall" style={styles.transactionRef}>
                  Ref: {item.reference}
                </Text>
              )}
            </View>
            <View style={styles.transactionRight}>
              <Text
                variant="titleMedium"
                style={[
                  styles.transactionAmount,
                  { color: isCredit ? "#10B981" : "#EF4444" },
                ]}
              >
                {isCredit ? "+" : "-"}₦{amount.toLocaleString()}
              </Text>
              <Chip
                mode="flat"
                style={[
                  styles.statusChip,
                  { backgroundColor: getStatusColor(item.status) + "20" },
                ]}
                textStyle={{ color: getStatusColor(item.status), fontSize: 11 }}
              >
                {item.status}
              </Chip>
            </View>
          </View>
          {item.narration && (
            <Text variant="bodySmall" style={styles.narration}>
              {item.narration}
            </Text>
          )}
        </Card.Content>
      </Card>
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Stats Cards */}
      <View style={styles.statsContainer}>
        <Card style={[styles.statCard, { backgroundColor: colors.primary }]}>
          <Card.Content>
            <Text style={styles.statLabel}>Total</Text>
            <Text style={styles.statValue}>{stats.total}</Text>
          </Card.Content>
        </Card>
        <Card style={[styles.statCard, { backgroundColor: "#10B981" }]}>
          <Card.Content>
            <Text style={styles.statLabel}>Reconciled</Text>
            <Text style={styles.statValue}>{stats.reconciled}</Text>
          </Card.Content>
        </Card>
        <Card style={[styles.statCard, { backgroundColor: "#F59E0B" }]}>
          <Card.Content>
            <Text style={styles.statLabel}>Pending</Text>
            <Text style={styles.statValue}>{stats.pending}</Text>
          </Card.Content>
        </Card>
        <Card style={[styles.statCard, { backgroundColor: "#EF4444" }]}>
          <Card.Content>
            <Text style={styles.statLabel}>Failed</Text>
            <Text style={styles.statValue}>{stats.failed}</Text>
          </Card.Content>
        </Card>
      </View>

      {/* Amount Summary */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Credit
              </Text>
              <Text
                variant="titleMedium"
                style={[styles.summaryValue, { color: "#10B981" }]}
              >
                ₦{stats.credit.toLocaleString()}
              </Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryItem}>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Debit
              </Text>
              <Text
                variant="titleMedium"
                style={[styles.summaryValue, { color: "#EF4444" }]}
              >
                ₦{stats.debit.toLocaleString()}
              </Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryItem}>
              <Text variant="bodySmall" style={styles.summaryLabel}>
                Net
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                ₦{(stats.credit - stats.debit).toLocaleString()}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Period Selector */}
      <View style={styles.periodContainer}>
        <SegmentedButtons
          value={period}
          onValueChange={setPeriod}
          buttons={[
            { value: "today", label: "Today" },
            { value: "week", label: "Week" },
            { value: "month", label: "Month" },
          ]}
        />
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search transactions..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      {/* Transactions List */}
      <FlatList
        data={filteredTransactions}
        renderItem={renderTransactionItem}
        keyExtractor={(item, index) =>
          item.id || item.reference || index.toString()
        }
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="file-document-outline" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No transactions found
            </Text>
          </View>
        }
      />

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
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
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  statsContainer: {
    flexDirection: "row",
    padding: spacing.md,
    gap: spacing.sm,
  },
  statCard: {
    flex: 1,
  },
  statLabel: {
    color: "#fff",
    fontSize: 11,
    opacity: 0.9,
  },
  statValue: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "bold",
    marginTop: 4,
  },
  summaryCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-around",
  },
  summaryItem: {
    alignItems: "center",
    flex: 1,
  },
  summaryDivider: {
    width: 1,
    backgroundColor: "#E5E7EB",
  },
  summaryLabel: {
    color: "#6B7280",
  },
  summaryValue: {
    fontWeight: "600",
    marginTop: 4,
  },
  periodContainer: {
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  searchContainer: {
    backgroundColor: "#fff",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  searchBar: {
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  listContent: {
    padding: spacing.md,
  },
  transactionCard: {
    marginBottom: spacing.md,
  },
  transactionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  transactionInfo: {
    flex: 1,
  },
  transactionType: {
    fontWeight: "600",
  },
  transactionDate: {
    color: "#6B7280",
    marginTop: 2,
  },
  transactionRef: {
    color: "#9CA3AF",
    fontSize: 11,
    marginTop: 2,
  },
  transactionRight: {
    alignItems: "flex-end",
    gap: spacing.xs,
  },
  transactionAmount: {
    fontWeight: "bold",
  },
  statusChip: {
    height: 24,
  },
  narration: {
    color: "#374151",
    marginTop: spacing.sm,
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
});
