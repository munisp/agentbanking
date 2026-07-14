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
    Button,
    Card,
    Chip,
    Searchbar,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, ledgerApi } from "../../services/apiService";
import { spacing } from "../../theme";

export default function TransactionsScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [transactions, setTransactions] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [userAccountNumbers, setUserAccountNumbers] = useState([]);
  const [stats, setStats] = useState({
    totalAmount: 0,
    totalCount: 0,
    successCount: 0,
  });

  useEffect(() => {
    fetchUserAccounts();
  }, []);

  useEffect(() => {
    if (userAccountNumbers.length > 0) {
      loadTransactions(true);
    }
  }, [filter, userAccountNumbers]);

  const fetchUserAccounts = async () => {
    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        setError("No keycloak ID found. Please log in again.");
        return;
      }

      const res = await accountApi.getAccountByKeycloakId(keycloakId);

      // The endpoint returns a single account object or an array
      const accountsData = Array.isArray(res)
        ? res
        : res.account
          ? [res.account]
          : res.accounts || res.data || [];

      const accountNumbers = accountsData.map((acc) => acc.account_number);
      setUserAccountNumbers(accountNumbers);
    } catch (err) {
      console.error("Failed to fetch user accounts:", err);
      setError(err?.message || "Failed to load account information");
    }
  };

  const loadTransactions = async (isRefresh = false) => {
    if (loading || (!isRefresh && !hasMore)) return;

    try {
      setLoading(true);
      setError("");

      if (userAccountNumbers.length === 0) {
        setTransactions([]);
        setLoading(false);
        return;
      }

      const currentPage = isRefresh ? 1 : page;

      // Use the first account number (agents typically have one account)
      const accountNumber = userAccountNumbers[0];

      const response = await ledgerApi.getTransactionsByAccountNumber(
        accountNumber,
        50,
        currentPage,
      );

      // The endpoint returns transactions filtered by account number
      let userTransactions = response.transactions ?? response ?? [];

      // Normalize transaction data and determine type
      const normalizedTransactions = userTransactions.map((txn) => {
        // Determine if user is receiving or sending money
        const isCredit = userAccountNumbers.includes(txn.payee_account_number);
        const isDebit = userAccountNumbers.includes(txn.payer_account_number);

        return {
          id: txn.id || txn.transaction_id,
          transaction_id: txn.transaction_id,
          type: isCredit ? "credit" : "debit",
          amount: parseFloat(txn.amount || 0),
          status: txn.status || "completed",
          date: txn.created_at || new Date().toISOString(),
          payer_account_number: txn.payer_account_number,
          payee_account_number: txn.payee_account_number,
          payer: txn.payer || txn.payer_name,
          payee: txn.payee || txn.payee_name,
          note: txn.note || txn.description,
          reference: txn.reference || txn.transaction_reference,
          currency: txn.currency || "NGN",
          // Display name: show counterparty
          recipient: isCredit
            ? txn.payer_name || txn.payer || "Unknown"
            : txn.payee_name || txn.payee || "Unknown",
        };
      });

      // Filter by type if needed
      let filteredData = normalizedTransactions;
      if (filter === "credit") {
        filteredData = normalizedTransactions.filter(
          (t) => t.type === "credit",
        );
      } else if (filter === "debit") {
        filteredData = normalizedTransactions.filter((t) => t.type === "debit");
      }

      if (isRefresh) {
        setTransactions(filteredData);
        setPage(2);
      } else {
        setTransactions((prev) => [...prev, ...filteredData]);
        setPage(currentPage + 1);
      }

      setHasMore(normalizedTransactions.length === 50);

      // Calculate stats
      if (isRefresh) {
        const totalAmount = normalizedTransactions.reduce(
          (sum, t) => sum + t.amount,
          0,
        );
        const successCount = normalizedTransactions.filter(
          (t) => t.status === "completed" || t.status === "success",
        ).length;

        setStats({
          totalAmount,
          totalCount: normalizedTransactions.length,
          successCount,
        });
      }
    } catch (error) {
      console.error("Error loading transactions:", error);
      setError(error?.message || "Failed to load transactions");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    setPage(1);
    setHasMore(true);
    loadTransactions(true);
  };

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    switch (statusLower) {
      case "completed":
      case "success":
      case "successful":
        return "#10B981";
      case "pending":
      case "processing":
        return "#F59E0B";
      case "failed":
      case "rejected":
        return "#EF4444";
      default:
        return "#6B7280";
    }
  };

  const filteredTransactions = transactions.filter((txn) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        txn.recipient?.toLowerCase().includes(query) ||
        txn.reference?.toLowerCase().includes(query) ||
        txn.note?.toLowerCase().includes(query) ||
        txn.transaction_id?.toLowerCase().includes(query) ||
        txn.amount?.toString().includes(query)
      );
    }
    return true;
  });

  const renderTransaction = ({ item }) => (
    <Card
      style={styles.transactionCard}
      onPress={() =>
        navigation.navigate("TransactionDetail", { transaction: item })
      }
    >
      <Card.Content>
        <View style={styles.transactionRow}>
          <View style={styles.transactionIcon}>
            <Icon
              name={item.type === "credit" ? "arrow-down" : "arrow-up"}
              size={24}
              color={item.type === "credit" ? "#10B981" : "#EF4444"}
            />
          </View>
          <View style={styles.transactionInfo}>
            <Text variant="bodyLarge" style={styles.transactionName}>
              {item.recipient}
            </Text>
            <Text variant="bodySmall" style={styles.transactionDate}>
              {new Date(item.date).toLocaleString()}
            </Text>
            {item.reference && (
              <Text variant="bodySmall" style={styles.transactionReference}>
                Ref: {item.reference}
              </Text>
            )}
          </View>
          <View style={styles.transactionAmount}>
            <Text
              variant="titleMedium"
              style={[
                styles.amount,
                item.type === "credit" ? styles.credit : styles.debit,
              ]}
            >
              {item.type === "credit" ? "+" : "-"}₦
              {Math.abs(item.amount).toLocaleString()}
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
      </Card.Content>
    </Card>
  );

  if (loading && !refreshing && transactions.length === 0) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>Loading transactions...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Stats Cards */}
      <View style={styles.statsContainer}>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            Total Transactions
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            {stats.totalCount}
          </Text>
        </View>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            Total Volume
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            ₦{(stats.totalAmount / 1000).toFixed(1)}K
          </Text>
        </View>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            Success Rate
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            {stats.totalCount > 0
              ? Math.round((stats.successCount / stats.totalCount) * 100)
              : 0}
            %
          </Text>
        </View>
      </View>

      {/* Search Bar */}
      <Searchbar
        placeholder="Search transactions..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
      />

      {/* Filter Buttons */}
      <SegmentedButtons
        value={filter}
        onValueChange={setFilter}
        style={styles.filterButtons}
        buttons={[
          { value: "all", label: "All" },
          { value: "credit", label: "Credits", icon: "arrow-down" },
          { value: "debit", label: "Debits", icon: "arrow-up" },
        ]}
      />

      {/* Transactions List */}
      {error && transactions.length === 0 ? (
        <View style={styles.errorContainer}>
          <Icon name="alert-circle-outline" size={48} color="#EF4444" />
          <Text style={styles.errorText}>{error}</Text>
          <Button
            mode="contained"
            onPress={onRefresh}
            style={styles.retryButton}
          >
            Retry
          </Button>
        </View>
      ) : filteredTransactions.length === 0 && !loading ? (
        <View style={styles.emptyContainer}>
          <Icon name="receipt" size={64} color="#9CA3AF" />
          <Text style={styles.emptyText}>No transactions found</Text>
          <Text style={styles.emptySubtext}>
            Your transactions will appear here
          </Text>
        </View>
      ) : (
        <FlatList
          data={filteredTransactions}
          renderItem={renderTransaction}
          keyExtractor={(item) =>
            item.id?.toString() || Math.random().toString()
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          onEndReached={() => {
            if (!loading && hasMore) {
              loadTransactions(false);
            }
          }}
          onEndReachedThreshold={0.5}
          ListFooterComponent={
            loading && transactions.length > 0 ? (
              <ActivityIndicator style={styles.footerLoader} />
            ) : null
          }
        />
      )}

      {/* Error Snackbar */}
      <Snackbar
        visible={!!error && transactions.length > 0}
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
    backgroundColor: "#F3F4F6",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#F3F4F6",
  },
  loadingText: {
    marginTop: spacing.md,
    color: "#6B7280",
  },
  statsContainer: {
    flexDirection: "row",
    padding: spacing.md,
    gap: spacing.sm,
  },
  statCard: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    padding: spacing.md,
    borderRadius: 12,
    elevation: 2,
  },
  statLabel: {
    color: "#6B7280",
    marginBottom: spacing.xs,
  },
  statValue: {
    fontWeight: "bold",
    color: "#1F2937",
  },
  searchBar: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    elevation: 2,
  },
  filterButtons: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  listContent: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  transactionCard: {
    marginBottom: spacing.sm,
    borderRadius: 12,
    elevation: 2,
  },
  transactionRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  transactionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  transactionInfo: {
    flex: 1,
  },
  transactionName: {
    fontWeight: "600",
    color: "#1F2937",
    marginBottom: 2,
  },
  transactionDate: {
    color: "#6B7280",
    fontSize: 12,
  },
  transactionReference: {
    color: "#9CA3AF",
    fontSize: 11,
    fontFamily: "monospace",
  },
  transactionAmount: {
    alignItems: "flex-end",
  },
  amount: {
    fontWeight: "bold",
    marginBottom: spacing.xs,
  },
  credit: {
    color: "#10B981",
  },
  debit: {
    color: "#EF4444",
  },
  statusChip: {
    height: 32,
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  errorText: {
    marginTop: spacing.md,
    marginBottom: spacing.lg,
    textAlign: "center",
    color: "#6B7280",
  },
  retryButton: {
    marginTop: spacing.md,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: "600",
    color: "#1F2937",
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: 14,
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  footerLoader: {
    marginVertical: spacing.md,
  },
});
