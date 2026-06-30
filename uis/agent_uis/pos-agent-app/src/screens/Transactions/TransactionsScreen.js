import { useFocusEffect } from "@react-navigation/native";
import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
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
    Button,
    Card,
    Chip,
    IconButton,
    Searchbar,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useTheme as useAppTheme } from "../../contexts/ThemeContext";
import {
  accountApi,
  agentApi,
  inventoryApi,
  ledgerApi,
} from "../../services/apiService";
import { spacing } from "../../theme";
import { printTransactionReceipt } from "../../utils/receiptPrinter";
/**
 * TransactionsScreen - Enhanced with patterns from core banking web/mobile app
 *
 * Improvements applied:
 * - Better transaction type detection using multiple fields (payer/payee account numbers)
 * - Robust data mapping with comprehensive fallbacks
 * - Status normalization (success -> completed)
 * - Enhanced recipient name resolution
 * - Better date/amount formatting
 * - Improved error handling with detailed messages
 */
export default function TransactionsScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { tenantConfig } = useAppTheme();
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
  const [agentData, setAgentData] = useState(null);
  const [printingTransactionId, setPrintingTransactionId] = useState(null);

  useEffect(() => {
    fetchUserAccounts();
    fetchAgentData();
  }, []);

  useEffect(() => {
    if (userAccountNumbers.length > 0) {
      console.log("User accounts loaded, fetching transactions...");
      loadTransactions(true);
    }
  }, [userAccountNumbers]); // Only reload when account numbers change

  // Refresh transactions when screen comes into focus
  useFocusEffect(
    React.useCallback(() => {
      console.log("TransactionsScreen focused - refreshing data");
      if (userAccountNumbers.length > 0) {
        loadTransactions(true);
      } else {
        fetchUserAccounts();
      }
    }, [userAccountNumbers]),
  );

  const fetchUserAccounts = async () => {
    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        setError("No keycloak ID found. Please log in again.");
        return;
      }

      console.log("Fetching account for keycloak ID:", keycloakId);
      const res = await accountApi.getAccountByKeycloakId(keycloakId);
      console.log("Account API response:", res);

      // The endpoint can return many shapes: account object, array, wrapped account(s)
      const accountsData = Array.isArray(res)
        ? res
        : Array.isArray(res?.accounts)
          ? res.accounts
          : Array.isArray(res?.data)
            ? res.data
            : Array.isArray(res?.data?.accounts)
              ? res.data.accounts
              : res?.account
                ? [res.account]
                : res?.data?.account
                  ? [res.data.account]
                  : res?.account_number || res?.data?.account_number
                    ? [res?.account_number ? res : res.data]
                    : [];

      const accountNumbers = accountsData
        .map((acc) => acc?.account_number)
        .filter(Boolean);

      // Mirror dashboard behavior: include store account numbers as well
      try {
        const storesResponse = await inventoryApi.getStores(keycloakId);
        const stores = Array.isArray(storesResponse?.data)
          ? storesResponse.data
          : Array.isArray(storesResponse)
            ? storesResponse
            : [];

        stores.forEach((store) => {
          if (store?.account_number) {
            accountNumbers.push(store.account_number);
          }
        });
      } catch (storesErr) {
        console.error("Failed to fetch store accounts:", storesErr);
      }

      const uniqueAccountNumbers = [...new Set(accountNumbers)];
      console.log("User account numbers:", uniqueAccountNumbers);
      if (uniqueAccountNumbers.length === 0) {
        console.warn("No account numbers found in account response:", res);
      }
      setUserAccountNumbers(uniqueAccountNumbers);
    } catch (err) {
      console.error("Failed to fetch user accounts:", err);
      setError(err?.message || "Failed to load account information");
    }
  };

  const fetchAgentData = async () => {
    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) return;

      const res = await agentApi.getAgentByKeycloakId(keycloakId);
      setAgentData(res.agent || res);
    } catch (err) {
      console.error("Failed to fetch agent data:", err);
    }
  };

  const handlePrintReceipt = async (transaction) => {
    try {
      setPrintingTransactionId(transaction.transaction_id || transaction.id);

      await printTransactionReceipt(transaction, {
        storeName: agentData?.business_name || tenantConfig?.name || "Agent",
        agentName:
          agentData?.full_name ||
          agentData?.first_name + " " + agentData?.last_name,
        agentPhone: agentData?.phone_number,
        agentId: agentData?.agent_id,
        storeAddress: agentData?.address,
      });

      setError("");
      Alert.alert("Success", "Receipt printed successfully!");
    } catch (err) {
      console.error("Print error:", err);
      Alert.alert("Print Error", err.message || "Failed to print receipt");
    } finally {
      setPrintingTransactionId(null);
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
      console.log(
        `Fetching transactions for ${userAccountNumbers.length} account(s), page: ${currentPage}`,
      );

      // Mirror dashboard: fetch each account's ledger history and merge
      const responses = await Promise.all(
        userAccountNumbers.map((accountNumber) =>
          ledgerApi
            .getTransactionsByAccountNumber(accountNumber, 50, currentPage)
            .then((response) => ({ accountNumber, response }))
            .catch((err) => {
              console.error(
                `Failed fetching transactions for ${accountNumber}:`,
                err,
              );
              return { accountNumber, response: null };
            }),
        ),
      );

      const allTransactions = responses.flatMap(({ response, accountNumber }) => {
        const txns = Array.isArray(response?.transactions)
          ? response.transactions
          : Array.isArray(response?.data?.transactions)
            ? response.data.transactions
            : Array.isArray(response?.data)
              ? response.data
              : Array.isArray(response)
                ? response
                : [];

        return txns.map((txn) => ({ ...txn, _sourceAccount: accountNumber }));
      });

      console.log(
        "Raw transactions sample:",
        allTransactions.length > 0 ? allTransactions[0] : "No transactions",
      );
      console.log("Total transactions extracted:", allTransactions.length);

      // Validate response data
      if (!Array.isArray(allTransactions)) {
        console.warn(
          "Unexpected response format, expected array:",
          allTransactions,
        );
        setLoading(false);
        return;
      }

      console.log(
        `Loaded ${allTransactions.length} transactions from ledger API`,
      );

      // Normalize transaction data and determine type (using core banking web app pattern)
      const normalizedTransactions = allTransactions.map((txn) => {
        // Determine if user is receiving or sending money
        // Check both account numbers and payer/payee fields for robust detection
        const isCredit = userAccountNumbers.includes(txn.payee_account_number);
        const isDebit = userAccountNumbers.includes(txn.payer_account_number);

        const normalizedType = isCredit
          ? "credit"
          : isDebit
            ? "debit"
            : txn.type === "credit" || txn.type === "debit"
              ? txn.type
              : "unknown";

        // Normalize status (map 'success' to 'completed', etc.)
        let normalizedStatus = txn.status?.toLowerCase() || "completed";
        if (
          normalizedStatus === "success" ||
          normalizedStatus === "successful"
        ) {
          normalizedStatus = "completed";
        }

        // Determine recipient name with more fallbacks
        let recipientName = "Unknown";
        if (isCredit) {
          // For credits, show who sent the money
          recipientName =
            txn.payer_name || txn.payer || txn.sender_name || "Unknown Sender";
        } else {
          // For debits, show who received the money
          recipientName =
            txn.payee_name ||
            txn.payee ||
            txn.recipient_name ||
            "Unknown Recipient";
        }

        // Better description handling
        const description =
          txn.note || txn.description || txn.narration || "Transaction";

        return {
          id: txn.id || txn.transaction_id,
          transaction_id: txn.transaction_id || txn.id,
          type: normalizedType,
          amount: parseFloat(txn.amount?.toString() || "0"),
          status: normalizedStatus,
          date: txn.created_at || txn.createdAt || new Date().toISOString(),
          payer_account_number: txn.payer_account_number,
          payee_account_number: txn.payee_account_number,
          payer: txn.payer || txn.payer_name,
          payee: txn.payee || txn.payee_name,
          note: description,
          reference:
            txn.reference || txn.transaction_reference || txn.transaction_id,
          currency: txn.currency || "NGN",
          balance_before: txn.balance_before ?? txn.balanceBefore ?? null,
          balance_after: txn.balance_after ?? txn.balanceAfter ?? null,
          // Display name: show counterparty
          recipient: recipientName,
        };
      });

      console.log(
        "Normalized transactions sample:",
        normalizedTransactions.length > 0
          ? normalizedTransactions[0]
          : "No transactions",
      );
      console.log(
        "Total normalized transactions:",
        normalizedTransactions.length,
      );

      // Remove duplicates based on transaction_id and sort by date (newest first)
      const uniqueTransactions = normalizedTransactions.reduce((acc, txn) => {
        const id = txn.transaction_id || txn.id;
        if (!acc.some((t) => (t.transaction_id || t.id) === id)) {
          acc.push(txn);
        }
        return acc;
      }, []);

      // Sort by date (newest first)
      uniqueTransactions.sort((a, b) => {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return dateB - dateA;
      });

      console.log(
        `After deduplication: ${uniqueTransactions.length} unique transactions`,
      );

      // Store ALL transactions without filtering
      if (isRefresh) {
        console.log(
          `Setting ${uniqueTransactions.length} transactions (refresh)`,
        );
        console.log(
          "Sample transaction being set:",
          uniqueTransactions.length > 0
            ? uniqueTransactions[0]
            : "No transactions",
        );
        setTransactions(uniqueTransactions);
        setPage(2);
      } else {
        console.log(`Appending ${uniqueTransactions.length} more transactions`);
        setTransactions((prev) => {
          // Deduplicate when appending
          const combined = [...prev, ...uniqueTransactions];
          return combined.reduce((acc, txn) => {
            const id = txn.transaction_id || txn.id;
            if (!acc.some((t) => (t.transaction_id || t.id) === id)) {
              acc.push(txn);
            }
            return acc;
          }, []);
        });
        setPage(currentPage + 1);
      }

      setHasMore(allTransactions.length === 50);
      console.log(
        `Transaction state updated. Total stored: ${uniqueTransactions.length}`,
      );

      // Calculate stats from all transactions
      if (isRefresh) {
        const totalAmount = uniqueTransactions.reduce(
          (sum, t) => sum + t.amount,
          0,
        );
        const successCount = uniqueTransactions.filter(
          (t) => t.status === "completed" || t.status === "success",
        ).length;

        setStats({
          totalAmount,
          totalCount: uniqueTransactions.length,
          successCount,
        });
      }
    } catch (error) {
      console.error("Error loading transactions:", error);
      // Provide more detailed error message
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to load transactions. Please check your connection and try again.";
      setError(errorMessage);
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

  // Format transaction amount with proper sign and currency
  const formatAmount = (amount, type, currency = "NGN") => {
    const sign = type === "credit" ? "+" : "-";
    const symbol = currency === "NGN" ? "₦" : currency;
    return `${sign}${symbol}${Math.abs(amount).toLocaleString()}`;
  };

  // Format date to more readable format
  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) {
        return dateString; // Return original if invalid
      }
      return date.toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return dateString;
    }
  };

  const filteredTransactions = transactions.filter((txn) => {
    // First apply type filter
    if (filter === "credit" && txn.type !== "credit") return false;
    if (filter === "debit" && txn.type !== "debit") return false;

    // Then apply search query
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

  console.log(
    `Total stored transactions: ${transactions.length}, Filtered: ${filteredTransactions.length}, Filter: ${filter}, Search: ${searchQuery}`,
  );

  // Calculate filtered stats for display
  const filteredStats = {
    totalCount: filteredTransactions.length,
    totalAmount: filteredTransactions.reduce((sum, t) => sum + t.amount, 0),
    successCount: filteredTransactions.filter(
      (t) => t.status === "completed" || t.status === "success",
    ).length,
  };

  const renderTransaction = ({ item }) => {
    console.log(
      `🎨 Rendering transaction: ${item.transaction_id || item.id} - ${item.recipient}`,
    );
    const isPrinting =
      printingTransactionId === (item.transaction_id || item.id);

    return (
      <Card style={styles.transactionCard}>
        <Card.Content>
          <TouchableOpacity
            onPress={() =>
              navigation.navigate("TransactionDetail", { transaction: item })
            }
            style={styles.transactionTouchable}
          >
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
                  {formatDate(item.date)}
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
                  {formatAmount(item.amount, item.type, item.currency)}
                </Text>
                {/* <Chip
                  mode="flat"
                  style={[
                    styles.statusChip,
                    { backgroundColor: getStatusColor(item.status) + "20" },
                  ]}
                  textStyle={{
                    color: getStatusColor(item.status),
                    fontSize: 14,
                  }} */}
                {/* > */}
                <Text>{item.status}</Text>
                {/* </Chip> */}
              </View>
            </View>
          </TouchableOpacity>
          <View style={styles.transactionActions}>
            <IconButton
              icon="printer"
              size={15}
              onPress={() => handlePrintReceipt(item)}
              disabled={isPrinting}
              loading={isPrinting}
              mode="contained-tonal"
              containercolor={colors.primary}
              iconColor="#FFF"
            />
          </View>
        </Card.Content>
      </Card>
    );
  };

  if (loading && !refreshing && transactions.length === 0) {
    console.log("🔄 Showing initial loading screen");
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>Loading transactions...</Text>
      </View>
    );
  }

  console.log(
    `📊 Render check - error: ${!!error}, transactions: ${transactions.length}, filteredTransactions: ${filteredTransactions.length}, loading: ${loading}`,
  );

  return (
    <View style={styles.container}>
      {/* Stats Cards */}
      <View style={styles.statsContainer}>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            {filter === "all"
              ? "Total Transactions"
              : filter === "credit"
                ? "Credit Transactions"
                : "Debit Transactions"}
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            {filteredStats.totalCount}
          </Text>
        </View>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            Total Volume
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            ₦{(filteredStats.totalAmount / 1000).toFixed(1)}K
          </Text>
        </View>
        <View style={styles.statCard}>
          <Text variant="bodySmall" style={styles.statLabel}>
            Success Rate
          </Text>
          <Text variant="titleLarge" style={styles.statValue}>
            {filteredStats.totalCount > 0
              ? Math.round(
                  (filteredStats.successCount / filteredStats.totalCount) * 100,
                )
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
      {error && transactions.length === 0
        ? (() => {
            console.log("❌ Showing error state");
            return (
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
            );
          })()
        : filteredTransactions.length === 0 && !loading
          ? (() => {
              console.log("📭 Showing empty state");
              return (
                <View style={styles.emptyContainer}>
                  <Icon name="receipt" size={64} color="#9CA3AF" />
                  <Text style={styles.emptyText}>No transactions found</Text>
                  <Text style={styles.emptySubtext}>
                    Your transactions will appear here
                  </Text>
                </View>
              );
            })()
          : (() => {
              console.log(
                `📋 Showing FlatList with ${filteredTransactions.length} items`,
              );
              return (
                <FlatList
                  style={{ flex: 1 }}
                  data={filteredTransactions}
                  renderItem={renderTransaction}
                  keyExtractor={(item) =>
                    item.id?.toString() || Math.random().toString()
                  }
                  contentContainerStyle={styles.listContent}
                  showsVerticalScrollIndicator={false}
                  refreshControl={
                    <RefreshControl
                      refreshing={refreshing}
                      onRefresh={onRefresh}
                    />
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
              );
            })()}

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
  transactionTouchable: {
    width: "100%",
  },
  transactionRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  transactionActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: "#F3F4F6",
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
    height: 38,
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
