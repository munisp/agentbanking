import * as Clipboard from "expo-clipboard";
import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    RefreshControl,
    ScrollView,
    Share,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    Divider,
    IconButton,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import {
  accountApi,
  agentApi,
  inventoryApi,
  ledgerApi,
} from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
import { printTransactionReceipt } from "../../utils/receiptPrinter";
export default function CashInScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [recentDeposits, setRecentDeposits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [printingTransactionId, setPrintingTransactionId] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      if (!keycloakId) {
        Alert.alert("Error", "Session expired. Please login again.");
        return;
      }

      // Load agent data
      const agentResponse = await agentApi.getAgentByKeycloakId(keycloakId);
      setAgentData(agentResponse.agent || agentResponse);

      // Load account data
      const accountResponse =
        await accountApi.getAccountByKeycloakId(keycloakId);

      const accountsData = Array.isArray(accountResponse)
        ? accountResponse
        : Array.isArray(accountResponse?.accounts)
          ? accountResponse.accounts
          : Array.isArray(accountResponse?.data)
            ? accountResponse.data
            : Array.isArray(accountResponse?.data?.accounts)
              ? accountResponse.data.accounts
              : accountResponse?.account
                ? [accountResponse.account]
                : accountResponse?.data?.account
                  ? [accountResponse.data.account]
                  : accountResponse?.account_number ||
                      accountResponse?.data?.account_number
                    ? [
                        accountResponse?.account_number
                          ? accountResponse
                          : accountResponse.data,
                      ]
                    : [];

      const primaryAccount = accountsData.find((acc) => acc?.account_number);
      setAccountData(primaryAccount || null);

      const accountNumbers = accountsData
        .map((acc) => acc?.account_number)
        .filter(Boolean);

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

      const allAccountNumbers = [...new Set(accountNumbers)];

      // Load recent cash in transactions from ledger (same pattern as agent dashboard)
      try {
        if (allAccountNumbers.length === 0) {
          setRecentDeposits([]);
        } else {
          const responses = await Promise.all(
            allAccountNumbers.map((accountNumber) =>
              ledgerApi
                .getTransactionsByAccountNumber(accountNumber, 10, 1)
                .then((response) => ({ response }))
                .catch((err) => {
                  console.error(
                    `Failed fetching transactions for ${accountNumber}:`,
                    err,
                  );
                  return { response: null };
                }),
            ),
          );

          const allTransactions = responses.flatMap(({ response }) =>
            Array.isArray(response?.transactions)
              ? response.transactions
              : Array.isArray(response?.data?.transactions)
                ? response.data.transactions
                : Array.isArray(response?.data)
                  ? response.data
                  : Array.isArray(response)
                    ? response
                    : [],
          );

          const normalizeAccount = (value) =>
            String(value ?? "")
              .trim()
              .toLowerCase();

          const normalizedAccounts = new Set(
            allAccountNumbers.map((acc) => normalizeAccount(acc)),
          );

          // Transaction screen parity: credit if payee account is one of the user's accounts.
          const deposits = allTransactions.filter((txn) => {
            const payeeAccount = normalizeAccount(txn?.payee_account_number);
            return normalizedAccounts.has(payeeAccount);
          });

          setRecentDeposits(deposits);
        }
      } catch (txnErr) {
        console.error("Error loading cash in transactions:", txnErr);
        // Don't fail the entire screen if transactions can't be loaded
        setRecentDeposits([]);
      }
    } catch (err) {
      console.error("Error loading cash in data:", err);
      // Only show alert for critical errors (agent/account data)
      if (!agentData && !accountData) {
        Alert.alert(
          "Error",
          err.message || "Failed to load account data. Please try again.",
        );
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const onRefresh = useCallback(() => {
    loadData(true);
  }, [loadData]);

  const copyToClipboard = async (text, label) => {
    await Clipboard.setStringAsync(text);
    showSnackbar(`${label} copied to clipboard`);
  };

  const showSnackbar = (message) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  };

  const shareAccountDetails = async () => {
    try {
      const message = `Area Konnect by Fidelity Agent Wallet
      
Account Name: ${accountData?.account_name || "N/A"}
Account Number: ${accountData?.account_number || "N/A"}
Bank: Area Konnect by Fidelity

Transfer to this account to fund your agent wallet.`;

      await Share.share({
        message: message,
      });
    } catch (error) {
      console.error("Error sharing:", error);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "#10B981";
      case "pending":
        return "#F59E0B";
      case "failed":
        return "#EF4444";
      default:
        return "#6B7280";
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "check-circle";
      case "pending":
        return "clock-outline";
      case "failed":
        return "close-circle";
      default:
        return "information-outline";
    }
  };

  const handlePrintReceipt = async (transaction) => {
    try {
      const txnId = transaction.id || transaction.transaction_id;
      setPrintingTransactionId(txnId);

      // Convert cash in transaction to standard format
      const standardTransaction = {
        ...transaction,
        type: "credit",
        date: transaction.created_at || transaction.timestamp,
        amount: transaction.amount,
        status: transaction.status || "completed",
        reference: transaction.reference || transaction.transaction_id,
        recipient: accountData?.account_name || "Your Account",
      };

      await printTransactionReceipt(standardTransaction, {
        storeName: agentData?.business_name || "Area Konnect by Fidelity Agent",
        agentName:
          agentData?.full_name ||
          agentData?.first_name + " " + agentData?.last_name,
        agentPhone: agentData?.phone_number,
        agentId: agentData?.agent_id,
        storeAddress: agentData?.address,
      });

      showSnackbar("Receipt printed successfully!");
    } catch (err) {
      console.error("Print error:", err);
      Alert.alert("Print Error", err.message || "Failed to print receipt");
    } finally {
      setPrintingTransactionId(null);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header Card */}
        <Card style={styles.headerCard}>
          <Card.Content>
            <View style={styles.headerContent}>
              <Icon name="wallet-plus" size={40} color={colors.primary} />
              <View style={styles.headerText}>
                <Text style={styles.headerTitle}>Fund Your Wallet</Text>
                <Text style={styles.headerSubtitle}>
                  Transfer money to your agent wallet
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        {/* Balance Card */}
        <Card style={styles.balanceCard}>
          <Card.Content>
            <Text style={styles.balanceLabel}>Current Balance</Text>
            <Text style={styles.balanceAmount}>
              {formatCurrency(accountData?.balance || 0)}
            </Text>
            <View style={styles.balanceInfo}>
              <Icon name="information-outline" size={16} color="#6B7280" />
              <Text style={styles.balanceInfoText}>
                Transfer funds to add money to your wallet
              </Text>
            </View>
          </Card.Content>
        </Card>

        {/* Account Details Card */}
        <Card style={styles.accountCard}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Transfer To This Account</Text>
              <TouchableOpacity onPress={shareAccountDetails}>
                <Icon name="share-variant" size={24} color={colors.primary} />
              </TouchableOpacity>
            </View>

            <Divider style={styles.divider} />

            {/* Account Name */}
            <View style={styles.detailRow}>
              <View style={styles.detailLabel}>
                <Icon name="account" size={20} color="#6B7280" />
                <Text style={styles.labelText}>Account Name</Text>
              </View>
              <View style={styles.detailValueContainer}>
                <Text style={styles.detailValue}>
                  {"Ifegbesan Tanitoluwa" || "N/A"}
                </Text>
                <TouchableOpacity
                  onPress={() =>
                    copyToClipboard(accountData?.account_name, "Account Name")
                  }
                >
                  <Icon name="content-copy" size={18} color={colors.primary} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Account Number */}
            <View style={styles.detailRow}>
              <View style={styles.detailLabel}>
                <Icon name="numeric" size={20} color="#6B7280" />
                <Text style={styles.labelText}>Account Number</Text>
              </View>
              <View style={styles.detailValueContainer}>
                <Text style={styles.detailValue}>
                  {accountData?.account_number || "N/A"}
                </Text>
                <TouchableOpacity
                  onPress={() =>
                    copyToClipboard(
                      accountData?.account_number,
                      "Account Number",
                    )
                  }
                >
                  <Icon name="content-copy" size={18} color={colors.primary} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Bank Name */}
            <View style={styles.detailRow}>
              <View style={styles.detailLabel}>
                <Icon name="bank" size={20} color="#6B7280" />
                <Text style={styles.labelText}>Bank</Text>
              </View>
              <View style={styles.detailValueContainer}>
                <Text style={styles.detailValue}>Area Konnect by Fidelity</Text>
              </View>
            </View>

            <View style={styles.instructionBox}>
              <Icon
                name="information"
                size={20}
                color={colors.primary}
                style={styles.instructionIcon}
              />
              <Text style={styles.instructionText}>
                Use your bank app or USSD to transfer money to this account.
                Funds will reflect in your wallet within minutes.
              </Text>
            </View>

            <Button
              mode="contained"
              onPress={shareAccountDetails}
              style={styles.shareButton}
              icon="share-variant"
            >
              Share Account Details
            </Button>
          </Card.Content>
        </Card>

        {/* Recent Deposits */}
        <Card style={styles.transactionsCard}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Recent Deposits</Text>
              <Chip style={styles.countChip} textStyle={styles.countChipText}>
                {recentDeposits.length}
              </Chip>
            </View>

            {recentDeposits.length === 0 ? (
              <View style={styles.emptyState}>
                <Icon name="inbox" size={48} color="#D1D5DB" />
                <Text style={styles.emptyText}>No deposits yet</Text>
                <Text style={styles.emptySubtext}>
                  Your recent deposits will appear here
                </Text>
              </View>
            ) : (
              <View style={styles.transactionsList}>
                {recentDeposits.map((transaction, index) => {
                  const txnId =
                    transaction.id || transaction.transaction_id || index;
                  const isPrinting = printingTransactionId === txnId;

                  return (
                    <Card key={index} style={styles.transactionCard}>
                      <Card.Content>
                        <View style={styles.transactionRow}>
                          <View style={styles.transactionInfo}>
                            <View style={styles.transactionHeader}>
                              <Text
                                variant="bodyMedium"
                                style={styles.transactionAmount}
                              >
                                {formatCurrency(transaction.amount || 0)}
                              </Text>
                              <View style={styles.statusBadge}>
                                <Icon
                                  name={getStatusIcon(transaction.status)}
                                  size={14}
                                  color={getStatusColor(transaction.status)}
                                />
                                <Text
                                  variant="bodySmall"
                                  style={[
                                    styles.statusText,
                                    {
                                      color: getStatusColor(transaction.status),
                                    },
                                  ]}
                                >
                                  {transaction.status}
                                </Text>
                              </View>
                            </View>
                            <Text
                              variant="bodySmall"
                              style={styles.transactionDate}
                            >
                              {new Date(
                                transaction.created_at || transaction.timestamp,
                              ).toLocaleString("en-US", {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </Text>
                            {transaction.reference && (
                              <Text
                                variant="bodySmall"
                                style={styles.transactionRef}
                              >
                                Ref: {transaction.reference}
                              </Text>
                            )}
                          </View>
                          <IconButton
                            icon="printer"
                            size={20}
                            onPress={() => handlePrintReceipt(transaction)}
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
                })}
              </View>
            )}

            {recentDeposits.length > 0 && (
              <Button
                mode="text"
                onPress={() => navigation.navigate("Transactions")}
                style={styles.viewAllButton}
              >
                View All Transactions
              </Button>
            )}
          </Card.Content>
        </Card>

        {/* How It Works */}
        <Card style={styles.howItWorksCard}>
          <Card.Content>
            <Text style={styles.cardTitle}>How to Fund Your Wallet</Text>
            <Divider style={styles.divider} />

            <View style={styles.stepContainer}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>1</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>Open Your Bank App</Text>
                <Text style={styles.stepDescription}>
                  Launch your mobile banking app or dial your bank's USSD code
                </Text>
              </View>
            </View>

            <View style={styles.stepContainer}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>2</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>Make Transfer</Text>
                <Text style={styles.stepDescription}>
                  Transfer to the account number shown above
                </Text>
              </View>
            </View>

            <View style={styles.stepContainer}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>3</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>Funds Added</Text>
                <Text style={styles.stepDescription}>
                  Your wallet balance will update within 1-5 minutes
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>
      </ScrollView>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={3000}
        style={styles.snackbar}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#F9FAFB",
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: 16,
    color: "#6B7280",
  },
  scrollContent: {
    padding: spacing.md,
  },
  headerCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  headerContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerText: {
    marginLeft: spacing.md,
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#1E40AF",
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: "#2563EB",
  },
  balanceCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
    backgroundColor: "#FFFFFF",
  },
  balanceLabel: {
    fontSize: 14,
    color: "#6B7280",
    marginBottom: 4,
  },
  balanceAmount: {
    fontSize: 36,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: spacing.sm,
  },
  balanceInfo: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EFF6FF",
    padding: spacing.sm,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  balanceInfoText: {
    fontSize: 12,
    color: "#1E40AF",
    marginLeft: spacing.xs,
    flex: 1,
  },
  accountCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#111827",
  },
  divider: {
    marginVertical: spacing.md,
  },
  detailRow: {
    marginBottom: spacing.md,
  },
  detailLabel: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  labelText: {
    fontSize: 12,
    color: "#6B7280",
    marginLeft: spacing.xs,
    fontWeight: "500",
  },
  detailValueContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#F9FAFB",
    padding: spacing.sm,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  detailValue: {
    fontSize: 16,
    color: "#111827",
    fontWeight: "600",
    flex: 1,
  },
  instructionBox: {
    flexDirection: "row",
    backgroundColor: "#EFF6FF",
    padding: spacing.md,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#BFDBFE",
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  instructionIcon: {
    marginRight: spacing.sm,
    marginTop: 2,
  },
  instructionText: {
    flex: 1,
    fontSize: 13,
    color: "#1E40AF",
    lineHeight: 20,
  },
  shareButton: {
    marginTop: spacing.sm,
    backgroundColor: colors.primary,
  },
  transactionsCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
  },
  countChip: {
    backgroundColor: "#DBEAFE",
  },
  countChipText: {
    color: "#1E40AF",
    fontSize: 12,
    fontWeight: "bold",
  },
  emptyState: {
    alignItems: "center",
    paddingVertical: spacing.xl * 2,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#6B7280",
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: 14,
    color: "#9CA3AF",
    marginTop: spacing.xs,
  },
  dateText: {
    fontSize: 13,
    color: "#374151",
  },
  amountText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.primary,
  },
  statusContainer: {
    flexDirection: "row",
    alignItems: "center",
  },
  statusText: {
    fontSize: 11,
    fontWeight: "500",
    marginLeft: 4,
    textTransform: "capitalize",
  },
  viewAllButton: {
    marginTop: spacing.sm,
  },
  transactionsList: {
    gap: spacing.sm,
  },
  transactionCard: {
    marginBottom: spacing.sm,
    backgroundColor: "#FFFFFF",
    elevation: 1,
  },
  transactionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  transactionInfo: {
    flex: 1,
  },
  transactionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  transactionAmount: {
    fontSize: 16,
    fontWeight: "700",
    color: "#10B981",
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  transactionDate: {
    fontSize: 12,
    color: "#6B7280",
    marginBottom: 2,
  },
  transactionRef: {
    fontSize: 11,
    color: "#9CA3AF",
  },
  howItWorksCard: {
    marginBottom: spacing.xl,
    borderRadius: 12,
    elevation: 2,
  },
  stepContainer: {
    flexDirection: "row",
    marginBottom: spacing.md,
  },
  stepNumber: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  stepNumberText: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#FFFFFF",
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#111827",
    marginBottom: 4,
  },
  stepDescription: {
    fontSize: 13,
    color: "#6B7280",
    lineHeight: 18,
  },
  snackbar: {
    backgroundColor: colors.primary,
  },
});
