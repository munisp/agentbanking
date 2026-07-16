import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import {
    accountApi,
    loanApi,
    networkOperationsApi,
} from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function FloatManagementScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [amount, setAmount] = useState("");
  const [term, setTerm] = useState("12");
  const [floatBalance, setFloatBalance] = useState(0);
  const [creditLimit, setCreditLimit] = useState(0);
  const [accountNumber, setAccountNumber] = useState("");
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [accountD, setAccountD] = useState(null);

  useEffect(() => {
    fetchFloatData();
  }, []);

  const fetchFloatData = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      // Fetch cash position from network operations
      // try {
      //   const cashPosition =
      //     await networkOperationsApi.getAgentCashPosition(agentId);
      //   if (cashPosition) {
      //     setFloatBalance(
      //       parseFloat(
      //         cashPosition.available_balance || cashPosition.balance || 0,
      //       ),
      //     );
      //     setCreditLimit(parseFloat(cashPosition.credit_limit || 0));
      //   }
      // } catch (err) {
      //   console.log(
      //     "Cash position not available, trying account balance:",
      //     err.message,
      //   );
      // }

      // Fallback to account balance
      try {
        const accountData = await accountApi.getAccountByKeycloakId(keycloakId);
        setAccountD(accountData);
        if (accountData && accountData.length > 0) {
          const account = accountData?.account || accountData;
          console.log("Account data fetched:", account);
          setAccountNumber(account.account_number);
          if (floatBalance === 0) {
            setFloatBalance(
              parseFloat(account.balance || 100),
            );

          }
        }
      } catch (err) {
        console.log("Account balance not available:", err.message);
      }

      // Fetch loan applications (float requests)
      try {
        const loanApplicationsResponse = await loanApi.getLoanApplications(keycloakId);
        const loanApplications = Array.isArray(loanApplicationsResponse)
          ? loanApplicationsResponse
          : loanApplicationsResponse?.data || [];

        // Filter for float loans only
        const floatLoans = loanApplications.filter(
          (loan) =>
            loan.loan_purpose?.toLowerCase().includes("float") ||
            loan.loan_purpose?.toLowerCase() === "float loan",
        );
        setRequests(floatLoans);
      } catch (err) {
        console.log("Loan applications not available:", err.message);
      }
    } catch (err) {
      console.error("Float data fetch error:", err);
      setError(err.message || "Failed to load float data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchFloatData(true);
  };

  const handleRequestFloat = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      setError("Please enter a valid amount");
      return;
    }

    if (!term || parseFloat(term) <= 0) {
      setError("Please enter a valid repayment term");
      return;
    }

    try {
      setLoading(true);
      setError("");

      // Create loan application for float request
      await loanApi.createLoanApplication({
        loan_amount: parseFloat(amount),
        loan_purpose: "Float Loan",
        requested_term: parseFloat(term),
        // Credit assessment performed server-side by loan-service using agent KYC data
      });

      setSuccess(
        `Float request for ₦${parseFloat(amount).toLocaleString()} submitted successfully`,
      );
      setAmount("");
      setTerm("12");
      fetchFloatData();
    } catch (err) {
      console.error("Float request error:", err);
      setError(err.message || "Failed to request float");
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "completed")
      return "#10B981";
    if (statusLower === "rejected" || statusLower === "failed")
      return "#EF4444";
    if (statusLower === "pending") return "#F59E0B";
    return "#6B7280";
  };

  const renderRequestItem = ({ item }) => (
    <View style={styles.historyItem}>
      <View style={styles.requestLeft}>
        <Text variant="bodyMedium" style={styles.requestTitle}>
          Float Request — {item.loan_application_id || item.id || "N/A"}
        </Text>
        <Text variant="bodySmall" style={styles.historyDate}>
          {new Date(item.created_at || item.date).toLocaleDateString()}
        </Text>
        {(item.reference || item.requested_term) && (
          <Text variant="bodySmall" style={styles.requestRef}>
            {item.reference
              ? `Ref: ${item.reference}`
              : `${item.requested_term} months`}
            {item.requested_term &&
              item.LoanInterestRatePercent &&
              ` · Interest Rate: ${item.LoanInterestRatePercent}%`}
          </Text>
        )}
      </View>
      <View style={styles.historyRight}>
        <Text variant="bodyMedium" style={styles.historyAmount}>
          ₦{parseFloat(item.loan_amount || item.amount).toLocaleString()}
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
  );

  if (loading && !refreshing) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  const utilizationPercent =
    creditLimit > 0 ? Math.round((floatBalance / creditLimit) * 100) : 100;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Float Balance Card */}
      <Card style={styles.balanceCard}>
        <Card.Content>
          <View style={styles.balanceHeader}>
            <Icon name="wallet" size={32} color="#fff" />
            <Text variant="bodyMedium" style={styles.balanceLabel}>
              Available Float
              {/* {JSON.stringify(accountD) } */}
            </Text>
          </View>
          <Text variant="displaySmall" style={styles.balanceAmount}>
            {formatCurrency(accountD?.account?.balance ?? floatBalance)}
          </Text>
          {accountNumber && (
            <Text variant="bodySmall" style={styles.accountNumber}>
              Account: {accountD?.account?.account_number ?? accountNumber}
            </Text>
          )}
          <View style={styles.limitRow}>
            <Text variant="bodySmall" style={styles.limitText}>
              {/* Credit Limit: ₦{creditLimit.toLocaleString()} */}
            </Text>
            <Chip
              mode="flat"
              style={styles.utilizationChip}
              textStyle={{ fontSize: 11 }}
            >
              {utilizationPercent}% Available
            </Chip>
          </View>
        </Card.Content>
      </Card>

      {/* Float Request Card */}
      <Card style={styles.requestCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Request Float
          </Text>
          <Text variant="bodySmall" style={styles.cardSubtitle}>
            Request additional float to increase your transaction capacity
          </Text>
          <View style={styles.infoBox}>
            <Icon name="information-outline" size={16} color="#1F2937" />
            <Text variant="bodySmall" style={styles.infoText}>
              Loan Purpose: Float Request (Fixed)
            </Text>
          </View>
          <TextInput
            label="Amount"
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
            mode="outlined"
            style={styles.input}
            left={<TextInput.Icon icon="currency-ngn" />}
            placeholder="Min: 10,000 • Max: 5,000,000"
          />
          <TextInput
            label="Repayment Period (months)"
            value={term}
            onChangeText={setTerm}
            keyboardType="numeric"
            mode="outlined"
            style={styles.input}
            left={<TextInput.Icon icon="calendar-month" />}
            placeholder="e.g., 12"
          />
          <Text variant="bodySmall" style={styles.noteText}>
            Your application will be reviewed based on your transaction history
            and account standing. You'll be notified once approved.
          </Text>
          <Button
            mode="contained"
            onPress={handleRequestFloat}
            disabled={!amount || !term || loading}
            style={styles.button}
            loading={loading}
          >
            Submit Float Request
          </Button>
        </Card.Content>
      </Card>

      {/* Recent Requests */}
      <Card style={styles.historyCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Recent Requests
          </Text>
          {requests.length > 0 ? (
            <FlatList
              data={requests}
              renderItem={renderRequestItem}
              keyExtractor={(item, index) =>
                item.id || item.reference || index.toString()
              }
              scrollEnabled={false}
            />
          ) : (
            <View style={styles.emptyRequests}>
              <Icon name="history" size={48} color="#D1D5DB" />
              <Text variant="bodyMedium" style={styles.emptyText}>
                No float requests yet
              </Text>
            </View>
          )}
        </Card.Content>
      </Card>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
      <Snackbar
        visible={!!success}
        onDismiss={() => setSuccess("")}
        duration={3000}
        style={{ backgroundColor: "#10B981" }}
      >
        {success}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  balanceCard: {
    marginBottom: spacing.md,
    backgroundColor: colors.primary,
  },
  balanceHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  balanceLabel: {
    color: "#fff",
    opacity: 0.9,
  },
  balanceAmount: {
    color: "#fff",
    fontWeight: "bold",
    marginTop: spacing.sm,
  },
  accountNumber: {
    color: "#fff",
    opacity: 0.8,
    marginTop: spacing.xs,
  },
  limitRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.md,
  },
  limitText: {
    color: "#fff",
    opacity: 0.9,
  },
  utilizationChip: {
    backgroundColor: "#fff",
  },
  requestCard: {
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontWeight: "bold",
    marginBottom: spacing.sm,
  },
  cardSubtitle: {
    color: "#6B7280",
    marginBottom: spacing.md,
  },
  infoBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
    padding: spacing.sm,
    borderRadius: 8,
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  infoText: {
    flex: 1,
    color: "#1F2937",
    fontWeight: "500",
  },
  noteText: {
    color: "#6B7280",
    backgroundColor: "#F9FAFB",
    padding: spacing.sm,
    borderRadius: 8,
    marginBottom: spacing.md,
  },
  input: {
    marginBottom: spacing.md,
  },
  button: {
    marginTop: spacing.sm,
  },
  historyCard: {
    marginBottom: spacing.md,
  },
  historyItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  requestLeft: {
    flex: 1,
  },
  requestTitle: {
    fontWeight: "500",
  },
  historyDate: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  requestRef: {
    color: "#9CA3AF",
    fontSize: 11,
    marginTop: 2,
  },
  historyRight: {
    alignItems: "flex-end",
    gap: spacing.xs,
  },
  historyAmount: {
    fontWeight: "600",
  },
  statusChip: {
    height: 24,
  },
  emptyRequests: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  emptyText: {
    color: "#6B7280",
    marginTop: spacing.sm,
  },
});
