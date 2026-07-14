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
    DataTable,
    Divider,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, agentApi, ledgerApi } from "../../services/apiService";
import { useTheme as useAppTheme } from "../../contexts/ThemeContext";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function CashInScreen({
 navigation }) {
  const { colors } = useTheme();
  const { tenantConfig } = useAppTheme();
  const bankName = tenantConfig?.name ? `${tenantConfig.name} Microfinance Bank` : "54agent Microfinance Bank";
  const styles = makeStyles(colors);
  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [recentDeposits, setRecentDeposits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");

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
      const account = accountResponse.account || accountResponse;
      setAccountData(account);

      // Load recent deposits via ledger service using the account number
      if (account?.account_number) {
        const txnResponse = await ledgerApi.getTransactionsByAccountNumber(
          account.account_number,
          20,
          1,
        );
        const allTxns = txnResponse.transactions || txnResponse.data || txnResponse || [];
        // Filter to credit/deposit transactions only
        const deposits = allTxns.filter((t) => {
          const type = (t.transaction_type || t.type || "").toLowerCase();
          const direction = (t.direction || t.entry_type || "").toLowerCase();
          return (
            type.includes("cash_in") ||
            type.includes("deposit") ||
            type.includes("credit") ||
            direction === "credit" ||
            direction === "cr"
          );
        });
        setRecentDeposits(deposits.slice(0, 10));
      }
    } catch (err) {
      console.error("Error loading cash in data:", err);
      Alert.alert(
        "Error",
        err.message || "Failed to load data. Please try again.",
      );
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
      const message = `54agent Agent Wallet
      
Account Name: ${accountData?.account_name || "N/A"}
Account Number: ${accountData?.account_number || "N/A"}
Bank: ${bankName}

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
        return "help-circle";
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
                <Text style={styles.detailValue}>{bankName}</Text>
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
              <DataTable>
                <DataTable.Header>
                  <DataTable.Title style={{ flex: 2 }}>Date</DataTable.Title>
                  <DataTable.Title style={{ flex: 2 }}>Amount</DataTable.Title>
                  <DataTable.Title style={{ flex: 1.5 }}>
                    Status
                  </DataTable.Title>
                </DataTable.Header>

                {recentDeposits.map((transaction, index) => (
                  <DataTable.Row key={index}>
                    <DataTable.Cell style={{ flex: 2 }}>
                      <Text style={styles.dateText}>
                        {new Date(
                          transaction.created_at || transaction.timestamp,
                        ).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </Text>
                    </DataTable.Cell>
                    <DataTable.Cell style={{ flex: 2 }}>
                      <Text style={styles.amountText}>
                        {formatCurrency(transaction.amount || 0)}
                      </Text>
                    </DataTable.Cell>
                    <DataTable.Cell style={{ flex: 1.5 }}>
                      <View style={styles.statusContainer}>
                        <Icon
                          name={getStatusIcon(transaction.status)}
                          size={16}
                          color={getStatusColor(transaction.status)}
                        />
                        <Text
                          style={[
                            styles.statusText,
                            { color: getStatusColor(transaction.status) },
                          ]}
                        >
                          {transaction.status}
                        </Text>
                      </View>
                    </DataTable.Cell>
                  </DataTable.Row>
                ))}
              </DataTable>
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
