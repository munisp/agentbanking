import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    KeyboardAvoidingView,
    Modal,
    Platform,
    RefreshControl,
    ScrollView,
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
    Text,
    TextInput,
    useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, agentApi, ledgerApi } from "../../services/apiService";
import CardInputForm from "../../components/CardInputForm";
import {
    cancelNfcRead,
    initNfc,
    isNfcSupported,
    readCardNFC,
} from "../../services/cardReaderService";
import {
    printTransactionReceipt,
    shareTransactionReceipt,
} from "../../services/receiptService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function CashOutScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const theme = useTheme();
  const [step, setStep] = useState(1); // 1: Details, 2: Card Details, 3: Confirmation

  // Transaction details
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");

  // Customer card details
  const [cardNumber, setCardNumber] = useState("");
  const [cardProvider, setCardProvider] = useState("");
  const [accountType, setAccountType] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [cvv, setCvv] = useState("");
  const [pin, setPin] = useState("");

  // PIN entry display
  const [showPin, setShowPin] = useState(false);

  // NFC state
  const [nfcAvailable, setNfcAvailable] = useState(false);
  const [nfcScanning, setNfcScanning] = useState(false);

  // Receipt modal state
  const [receiptVisible, setReceiptVisible] = useState(false);
  const [receiptData, setReceiptData] = useState(null);
  const [receiptPrinting, setReceiptPrinting] = useState(false);

  const agentDataRef = useRef(null);

  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [recentWithdrawals, setRecentWithdrawals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [snackbarVisible, setSnackbarVisible] = useState(false);

  useEffect(() => {
    loadData();
    isNfcSupported().then((supported) => {
      setNfcAvailable(supported);
      if (supported) initNfc().catch(() => {});
    });
    return () => cancelNfcRead();
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
      const agent = agentResponse.agent || agentResponse;
      agentDataRef.current = agent;
      setAgentData(agent);

      // Load account data
      const accountResponse =
        await accountApi.getAccountByKeycloakId(keycloakId);
      const account = accountResponse.account || accountResponse;
      setAccountData(account);

      // Load recent withdrawals via ledger service
      if (account?.account_number) {
        const txnResponse = await ledgerApi.getTransactionsByAccountNumber(
          account.account_number,
          20,
          1,
        );
        const allTxns = txnResponse.transactions || txnResponse.data || txnResponse || [];
        const withdrawals = allTxns.filter((t) => {
          const type = (t.transaction_type || t.type || "").toLowerCase();
          const direction = (t.direction || t.entry_type || "").toLowerCase();
          return (
            type.includes("cash_out") ||
            type.includes("withdrawal") ||
            type.includes("debit") ||
            direction === "debit" ||
            direction === "dr"
          );
        });
        setRecentWithdrawals(withdrawals.slice(0, 10));
      }
    } catch (err) {
      console.error("Error loading cash out data:", err);
      showError(err.message || "Failed to load data. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const onRefresh = useCallback(() => {
    loadData(true);
  }, [loadData]);

  const showError = (message) => {
    setError(message);
    setSnackbarVisible(true);
  };

  const showSuccess = (message) => {
    setSuccess(message);
    setSnackbarVisible(true);
  };

  const detectCardProvider = (number) => {
    const cleaned = number.replace(/\s/g, "");
    if (
      cleaned.startsWith("4") ||
      cleaned.startsWith("50") ||
      cleaned.startsWith("65")
    ) {
      return "Verve";
    }
    if (cleaned.startsWith("5")) {
      return "Mastercard";
    }
    if (cleaned.startsWith("6")) {
      return "Verve";
    }
    return "";
  };

  const handleContinueToCard = () => {
    setError("");

    if (!amount || parseFloat(amount) <= 0) {
      showError("Please enter a valid withdrawal amount");
      return;
    }

    const amountInKobo = parseFloat(amount) * 100;
    if (accountData && amountInKobo > accountData.balance) {
      showError("Insufficient balance in your agent wallet");
      return;
    }

    setStep(2);
  };

  const handleNfcScan = async () => {
    setNfcScanning(true);
    setError("");
    try {
      const card = await readCardNFC();
      setCardNumber(card.cardNumber);
      setCardProvider(card.cardProvider);
      if (card.expiryDate) setExpiryDate(card.expiryDate);
      showSuccess("Card read successfully!");
    } catch (err) {
      showError(err.message || "NFC read failed. Please enter card details manually.");
    } finally {
      setNfcScanning(false);
    }
  };

  const handleSubmitWithdrawal = async () => {
    setError("");

    // Validate card details
    if (!cardNumber || cardNumber.length < 15) {
      showError("Please enter a valid card number");
      return;
    }
    if (!expiryDate || expiryDate.length < 7) {
      showError("Please enter card expiry date (MM / YY)");
      return;
    }
    if (!cvv || cvv.length < 3) {
      showError("Please enter CVV");
      return;
    }
    if (!accountType) {
      showError("Please select account type");
      return;
    }
    if (!pin || pin.length !== 4) {
      showError("Please enter 4-digit PIN");
      return;
    }

    setSubmitting(true);

    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      if (!keycloakId) {
        throw new Error("Session expired. Please login again.");
      }

      const txnRef = reference || `CASHOUT-${Date.now()}`;
      await accountApi.createCashOut({
        agent_id: keycloakId,
        customer_card_number: cardNumber,
        amount: parseFloat(amount),
        currency: "NGN",
        reference: txnRef,
        description: description || "Cash withdrawal",
        card_details: {
          card_number: cardNumber,
          expiry: expiryDate,
          cvv: cvv,
          account_type: accountType,
          pin: pin,
        },
      });

      // Show receipt modal
      const agent = agentDataRef.current;
      setReceiptData({
        type: "cashout",
        amount: parseFloat(amount),
        currency: "NGN",
        reference: txnRef,
        description: description || "Cash withdrawal",
        cardNumber,
        cardProvider,
        accountType,
        agentName: agent?.name || agent?.business_name || "Agent",
        agentId: keycloakId,
        timestamp: new Date().toISOString(),
      });
      setReceiptVisible(true);

      // Reset form
      setStep(1);
      setAmount("");
      setReference("");
      setDescription("");
      setCardNumber("");
      setCardProvider("");
      setAccountType("");
      setExpiryDate("");
      setCvv("");
      setPin("");
      loadData();
    } catch (err) {
      console.error("Cash out error:", err);
      showError(
        err.message || "Failed to process withdrawal. Please try again.",
      );
    } finally {
      setSubmitting(false);
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
        return theme.colors.error;
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
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : null}
    >
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
              <Icon name="cash-minus" size={40} color={theme.colors.primary} />
              <View style={styles.headerText}>
                <Text style={styles.headerTitle}>Cash Withdrawal</Text>
                <Text style={styles.headerSubtitle}>
                  Process customer cash withdrawal
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        {/* Balance Card */}
        <Card style={styles.balanceCard}>
          <Card.Content>
            <View style={styles.balanceRow}>
              <View>
                <Text style={styles.balanceLabel}>Your Agent Balance</Text>
                <Text style={styles.balanceAmount}>
                  {formatCurrency(accountData?.balance || 0)}
                </Text>
              </View>
              <Icon name="wallet" size={32} color={theme.colors.primary} />
            </View>
          </Card.Content>
        </Card>

        {/* Step 1: Amount */}
        {step === 1 && (
          <Card style={styles.formCard}>
            <Card.Content>
              <Text style={styles.cardTitle}>Enter Withdrawal Amount</Text>
              <Divider style={styles.divider} />

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Amount *</Text>
                <TextInput
                  mode="outlined"
                  value={amount}
                  onChangeText={setAmount}
                  placeholder="0.00"
                  keyboardType="numeric"
                  left={<TextInput.Icon icon="currency-ngn" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>

              {/*<View style={styles.inputGroup}>
                <Text style={styles.label}>Reference (Optional)</Text>
                <TextInput
                  mode="outlined"
                  value={reference}
                  onChangeText={setReference}
                  placeholder="Transaction reference"
                  left={<TextInput.Icon icon="pound" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>*/}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Description (Optional)</Text>
                <TextInput
                  mode="outlined"
                  value={description}
                  onChangeText={setDescription}
                  placeholder="Add a note"
                  multiline
                  numberOfLines={3}
                  left={<TextInput.Icon icon="note-text" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>

              <Button
                mode="contained"
                onPress={handleContinueToCard}
                style={styles.continueButton}
                icon="arrow-right"
                contentStyle={styles.buttonContent}
              >
                Continue to Card Details
              </Button>
            </Card.Content>
          </Card>
        )}

        {/* Step 2: Card Details */}
        {step === 2 && (
          <Card style={styles.formCard}>
            <Card.Content>
              <View style={styles.cardHeader}>
                <TouchableOpacity onPress={() => setStep(1)}>
                  <Icon name="arrow-left" size={24} color="#374151" />
                </TouchableOpacity>
                <Text style={styles.cardTitle}>Customer Card Details</Text>
                <View style={{ width: 24 }} />
              </View>

              <View style={styles.amountDisplay}>
                <Text style={styles.amountDisplayLabel}>Withdrawal Amount</Text>
                <Text style={styles.amountDisplayValue}>
                  {formatCurrency(parseFloat(amount))}
                </Text>
              </View>

              <Divider style={styles.divider} />

              {/* NFC Tap */}
              {nfcAvailable && (
                <TouchableOpacity
                  style={[
                    styles.nfcButton,
                    nfcScanning && styles.nfcButtonScanning,
                  ]}
                  onPress={handleNfcScan}
                  disabled={nfcScanning}
                >
                  {nfcScanning ? (
                    <>
                      <ActivityIndicator color={colors.primary} size="small" />
                      <Text style={styles.nfcButtonText}>Scanning — hold card to phone...</Text>
                    </>
                  ) : (
                    <>
                      <Icon name="contactless-payment" size={28} color={colors.primary} />
                      <Text style={styles.nfcButtonText}>Tap Card (NFC)</Text>
                    </>
                  )}
                </TouchableOpacity>
              )}

              {nfcAvailable && (
                <View style={styles.orDivider}>
                  <View style={styles.orLine} />
                  <Text style={styles.orText}>or enter manually</Text>
                  <View style={styles.orLine} />
                </View>
              )}

              <CardInputForm
                cardNumber={cardNumber}
                cardProvider={cardProvider}
                expiryDate={expiryDate}
                cvv={cvv}
                accountType={accountType}
                pin={pin}
                showPin={showPin}
                onCardNumberChange={(digits) => {
                  setCardNumber(digits);
                  setCardProvider(detectCardProvider(digits));
                }}
                onExpiryChange={setExpiryDate}
                onCvvChange={setCvv}
                onAccountTypeChange={setAccountType}
                onPinChange={setPin}
                onTogglePin={() => setShowPin((v) => !v)}
              />

              <Button
                mode="contained"
                onPress={handleSubmitWithdrawal}
                loading={submitting}
                disabled={submitting}
                style={styles.submitButton}
                icon="check"
                contentStyle={styles.buttonContent}
              >
                {submitting ? "Processing..." : "Process Withdrawal"}
              </Button>

              <Button
                mode="text"
                onPress={() => setStep(1)}
                style={styles.cancelButton}
              >
                Cancel
              </Button>
            </Card.Content>
          </Card>
        )}

        {/* Recent Withdrawals */}
        <Card style={styles.transactionsCard}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Recent Withdrawals</Text>
              <Chip style={styles.countChip} textStyle={styles.countChipText}>
                {recentWithdrawals.length}
              </Chip>
            </View>

            {recentWithdrawals.length === 0 ? (
              <View style={styles.emptyState}>
                <Icon name="inbox" size={48} color="#D1D5DB" />
                <Text style={styles.emptyText}>No withdrawals yet</Text>
                <Text style={styles.emptySubtext}>
                  Recent withdrawals will appear here
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

                {recentWithdrawals.map((transaction, index) => (
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

            {recentWithdrawals.length > 0 && (
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
      </ScrollView>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={3000}
        style={[
          styles.snackbar,
          error ? styles.snackbarError : styles.snackbarSuccess,
        ]}
      >
        {error || success}
      </Snackbar>

      {/* Receipt Modal */}
      <Modal
        visible={receiptVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setReceiptVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Icon name="check-circle" size={40} color="#10B981" />
              <Text style={styles.modalTitle}>Withdrawal Successful</Text>
              <Text style={styles.modalSubtitle}>
                {receiptData && formatCurrency(receiptData.amount)}
              </Text>
            </View>
            <Divider style={{ marginVertical: spacing.sm }} />
            {receiptData && (
              <View style={styles.receiptRows}>
                <View style={styles.receiptRow}>
                  <Text style={styles.receiptLabel}>Reference</Text>
                  <Text style={styles.receiptValue}>{receiptData.reference}</Text>
                </View>
                {receiptData.cardProvider ? (
                  <View style={styles.receiptRow}>
                    <Text style={styles.receiptLabel}>Card</Text>
                    <Text style={styles.receiptValue}>
                      **** {String(receiptData.cardNumber).slice(-4)}{" "}
                      ({receiptData.cardProvider})
                    </Text>
                  </View>
                ) : null}
                <View style={styles.receiptRow}>
                  <Text style={styles.receiptLabel}>Date</Text>
                  <Text style={styles.receiptValue}>
                    {new Date(receiptData.timestamp).toLocaleString("en-NG", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </Text>
                </View>
              </View>
            )}
            <Divider style={{ marginVertical: spacing.sm }} />
            <View style={styles.modalActions}>
              <Button
                mode="outlined"
                icon="share-variant"
                style={styles.modalBtn}
                loading={receiptPrinting}
                onPress={async () => {
                  setReceiptPrinting(true);
                  try {
                    await shareTransactionReceipt(receiptData);
                  } catch (e) {
                    showError(e.message || "Share failed");
                  } finally {
                    setReceiptPrinting(false);
                  }
                }}
              >
                Share
              </Button>
              <Button
                mode="outlined"
                icon="printer"
                style={styles.modalBtn}
                loading={receiptPrinting}
                onPress={async () => {
                  setReceiptPrinting(true);
                  try {
                    await printTransactionReceipt(receiptData);
                  } catch (e) {
                    showError(e.message || "Print failed");
                  } finally {
                    setReceiptPrinting(false);
                  }
                }}
              >
                Print
              </Button>
            </View>
            <Button
              mode="contained"
              style={styles.modalDoneBtn}
              onPress={() => setReceiptVisible(false)}
            >
              Done
            </Button>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
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
    backgroundColor: "#E8F4F8",
    borderWidth: 1,
    borderColor: "#B3D9E8",
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
    color: colors.primary,
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: colors.primary,
  },
  balanceCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
    backgroundColor: "#FFFFFF",
  },
  balanceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  balanceLabel: {
    fontSize: 14,
    color: "#6B7280",
    marginBottom: 4,
  },
  balanceAmount: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#111827",
  },
  formCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#111827",
  },
  divider: {
    marginVertical: spacing.md,
  },
  inputGroup: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#374151",
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: "#FFFFFF",
  },
  row: {
    flexDirection: "row",
  },
  amountDisplay: {
    backgroundColor: "#E8F4F8",
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#B3D9E8",
  },
  amountDisplayLabel: {
    fontSize: 12,
    color: colors.primary,
    marginBottom: 4,
    fontWeight: "600",
  },
  amountDisplayValue: {
    fontSize: 32,
    fontWeight: "bold",
    color: colors.primary,
  },
  accountTypeContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  accountTypeChip: {
    backgroundColor: "#F3F4F6",
    marginRight: spacing.xs,
    marginBottom: spacing.xs,
  },
  accountTypeChipSelected: {
    backgroundColor: colors.primary,
  },
  accountTypeChipText: {
    color: "#6B7280",
  },
  accountTypeChipTextSelected: {
    color: "#FFFFFF",
  },
  securityInfo: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    padding: spacing.sm,
    borderRadius: 8,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  securityInfoText: {
    fontSize: 12,
    color: "#047857",
    marginLeft: spacing.xs,
    flex: 1,
    fontWeight: "500",
  },
  continueButton: {
    backgroundColor: colors.primary,
    marginTop: spacing.sm,
  },
  submitButton: {
    backgroundColor: colors.primary,
  },
  cancelButton: {
    marginTop: spacing.sm,
  },
  buttonContent: {
    height: 48,
  },
  transactionsCard: {
    marginBottom: spacing.xl,
    borderRadius: 12,
    elevation: 2,
  },
  countChip: {
    backgroundColor: "#E8F4F8",
  },
  countChipText: {
    color: colors.primary,
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
  snackbar: {
    marginBottom: spacing.md,
  },
  snackbarSuccess: {
    backgroundColor: "#10B981",
  },
  snackbarError: {
    backgroundColor: "#B91C1C",
  },
  nfcButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderWidth: 2,
    borderColor: colors.primary,
    borderStyle: "dashed",
    borderRadius: 12,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: "#EFF6FF",
  },
  nfcButtonScanning: {
    borderStyle: "solid",
    backgroundColor: "#DBEAFE",
  },
  nfcButtonText: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.primary,
  },
  orDivider: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  orLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#D1D5DB",
  },
  orText: {
    fontSize: 12,
    color: "#9CA3AF",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#FFF",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: spacing.lg,
  },
  modalHeader: {
    alignItems: "center",
    paddingVertical: spacing.md,
    gap: spacing.xs,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#111827",
  },
  modalSubtitle: {
    fontSize: 28,
    fontWeight: "900",
    color: colors.primary,
  },
  receiptRows: {
    gap: spacing.xs,
  },
  receiptRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  receiptLabel: {
    color: "#6B7280",
    fontSize: 13,
  },
  receiptValue: {
    fontWeight: "600",
    fontSize: 13,
    color: "#111827",
    maxWidth: "60%",
    textAlign: "right",
  },
  modalActions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  modalBtn: {
    flex: 1,
  },
  modalDoneBtn: {
    backgroundColor: colors.primary,
  },
});
