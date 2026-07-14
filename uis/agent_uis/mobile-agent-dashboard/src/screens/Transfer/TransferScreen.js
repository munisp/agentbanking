import * as SecureStore from "expo-secure-store";
import React, { useEffect, useRef, useState } from "react";
import {
    Alert,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    ActivityIndicator,
    Button,
    Card,
    Divider,
    SegmentedButtons,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, agentApi, inventoryApi } from "../../services/apiService";
import transactionService from "../../services/transactionService";
import { spacing } from "../../theme";

export default function TransferScreen({ navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const lookupTimer = useRef(null);

  const [transferType, setTransferType] = useState("inbound");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [account, setAccount] = useState(null);
  const [sourceAccounts, setSourceAccounts] = useState([]);
  const [selectedSourceAccountNumber, setSelectedSourceAccountNumber] = useState("");
  const [isLoadingSourceAccounts, setIsLoadingSourceAccounts] = useState(false);
  const [banks, setBanks] = useState([]);
  const [isLoadingBanks, setIsLoadingBanks] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarType, setSnackbarType] = useState("success");

  // Recipient name lookup state
  const [recipientName, setRecipientName] = useState("");
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState("");

  const [formData, setFormData] = useState({
    recipientAccountNumber: "",
    amount: "",
    description: "",
    beneficiaryName: "",
    beneficiaryBank: "",
    beneficiaryBankCode: "",
    pin: "",
  });

  useEffect(() => {
    fetchAgentAccount();
    loadSourceAccounts();
    loadBanks();
  }, []);

  // Auto-lookup account name when account number reaches 10 digits
  useEffect(() => {
    const acctNum = formData.recipientAccountNumber.trim();
    setRecipientName("");
    setLookupError("");

    if (acctNum.length < 10) return;

    clearTimeout(lookupTimer.current);
    lookupTimer.current = setTimeout(() => {
      lookupRecipient(acctNum);
    }, 500);

    return () => clearTimeout(lookupTimer.current);
  }, [formData.recipientAccountNumber]);

  const lookupRecipient = async (accountNumber) => {
    try {
      setIsLookingUp(true);
      setLookupError("");
      const res = await accountApi.getAccountByAccountNumber(accountNumber);
      const acc = res?.account || res;
      const name =
        acc?.account_name ||
        acc?.full_name ||
        [acc?.first_name, acc?.last_name].filter(Boolean).join(" ") ||
        acc?.name;
      if (name) {
        setRecipientName(name);
        // Auto-fill beneficiary name for outbound transfers
        if (transferType === "outbound") {
          setFormData((prev) => ({ ...prev, beneficiaryName: name }));
        }
      } else {
        setLookupError("Account found but name unavailable");
      }
    } catch {
      setLookupError("Account not found");
    } finally {
      setIsLookingUp(false);
    }
  };

  const loadSourceAccounts = async () => {
    try {
      setIsLoadingSourceAccounts(true);
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) return;

      const all = [];

      // 1. Agent's own account
      try {
        const res = await accountApi.getAccountByKeycloakId(keycloakId);
        const acc = res?.account || res;
        if (acc?.account_number) {
          all.push({
            ...acc,
            display_name: acc.account_name || acc.full_name ||
              [acc.first_name, acc.last_name].filter(Boolean).join(" ") ||
              "Agent Account",
            owner_type: "agent",
          });
        }
      } catch (e) {
        console.log("Agent account fetch failed:", e.message);
      }

      // 2. Inventory stores
      try {
        const storesRes = await inventoryApi.getStores(keycloakId);
        const stores = Array.isArray(storesRes)
          ? storesRes
          : storesRes?.data || storesRes?.stores || [];
        await Promise.all(
          stores.map(async (store) => {
            if (!store.account_number) return;
            try {
              const accRes = await accountApi.getAccountByAccountNumber(store.account_number);
              const acc = accRes?.account || accRes;
              if (acc?.account_number) {
                all.push({
                  ...acc,
                  display_name: store.name || store.store_name || acc.account_name || "Store",
                  owner_type: "store",
                });
              }
            } catch {}
          })
        );
      } catch (e) {
        console.log("Inventory stores fetch failed:", e.message);
      }

      // 3. Agent businesses
      try {
        const bizRes = await agentApi.getAgentBusinesses(keycloakId);
        const businesses = Array.isArray(bizRes)
          ? bizRes
          : bizRes?.data || bizRes?.businesses || [];
        await Promise.all(
          businesses.map(async (biz) => {
            const acctNum = biz.account_number || biz.business_account_number;
            if (!acctNum) return;
            // Skip if already added from inventory
            if (all.some((a) => a.account_number === acctNum)) return;
            try {
              const accRes = await accountApi.getAccountByAccountNumber(acctNum);
              const acc = accRes?.account || accRes;
              if (acc?.account_number) {
                all.push({
                  ...acc,
                  display_name: biz.business_name || biz.name || acc.account_name || "Business",
                  owner_type: "business",
                });
              }
            } catch {}
          })
        );
      } catch (e) {
        console.log("Agent businesses fetch failed:", e.message);
      }

      setSourceAccounts(all);
      if (all.length > 0) {
        setSelectedSourceAccountNumber(all[0].account_number);
      }
    } catch (error) {
      console.error("Error loading source accounts:", error);
    } finally {
      setIsLoadingSourceAccounts(false);
    }
  };

  const loadBanks = async () => {
    try {
      setIsLoadingBanks(true);
      const response = await accountApi.getBanks();
      const bankList =
        response?.banks || response?.data?.banks || response?.data || [];
      setBanks(Array.isArray(bankList) ? bankList : []);
    } catch (error) {
      console.error("Error loading banks:", error);
    } finally {
      setIsLoadingBanks(false);
    }
  };

  const fetchAgentAccount = async () => {
    try {
      setLoading(true);
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) throw new Error("Not authenticated");

      const response = await accountApi.getAccountByKeycloakId(keycloakId);
      const accountData = Array.isArray(response)
        ? response[0]
        : response.account || response;
      setAccount(accountData);
    } catch (error) {
      console.error("Error fetching account:", error);
      Alert.alert("Error", "Failed to load your account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleTransfer = async () => {
    const selectedSourceAccount =
      sourceAccounts.find((item) => item.account_number === selectedSourceAccountNumber) || account;

    if (!selectedSourceAccount?.account_number) {
      Alert.alert("Error", "Account not loaded. Please refresh.");
      return;
    }
    if (!formData.recipientAccountNumber.trim()) {
      Alert.alert("Error", "Please enter recipient account number");
      return;
    }
    if (!formData.amount || parseFloat(formData.amount) <= 0) {
      Alert.alert("Error", "Please enter a valid amount");
      return;
    }
    if (!formData.pin || formData.pin.length !== 4) {
      Alert.alert("Error", "Please enter a valid 4-digit PIN");
      return;
    }
    if (transferType === "outbound") {
      if (!formData.beneficiaryName.trim()) {
        Alert.alert("Error", "Please enter beneficiary name");
        return;
      }
      if (!formData.beneficiaryBankCode.trim()) {
        Alert.alert("Error", "Please select a bank");
        return;
      }
    }

    try {
      setSubmitting(true);

      if (transferType === "inbound") {
        const result = await transactionService.createInternalTransfer({
          from_account_number: selectedSourceAccount.account_number,
          to_account_number: formData.recipientAccountNumber,
          amount: formData.amount,
          currency: "NGN",
          description: formData.description || "Transfer between agents",
          pin: formData.pin,
        });

        setSnackbarMessage(
          result?.queued
            ? "No internet. Transfer queued and will sync automatically."
            : "Transfer successful!",
        );
        setSnackbarType("success");
      } else {
        const selectedBank = banks.find(
          (bank) => String(bank.code) === String(formData.beneficiaryBankCode),
        );
        if (!selectedBank) {
          Alert.alert("Error", "Please select a valid bank");
          return;
        }

        const result = await transactionService.createExternalTransfer({
          from_account_number: selectedSourceAccount.account_number,
          beneficiary_account_number: formData.recipientAccountNumber,
          beneficiary_name: formData.beneficiaryName,
          beneficiary_bank: selectedBank.name,
          beneficiary_bank_code: selectedBank.code,
          amount: formData.amount,
          currency: "NGN",
          narration: formData.description || "Transfer to external account",
          pin: formData.pin,
        });

        setSnackbarMessage(
          result?.queued
            ? "No internet. Transfer queued and will sync automatically."
            : "Transfer initiated successfully!",
        );
        setSnackbarType("success");
      }

      setSnackbarVisible(true);
      setFormData({
        recipientAccountNumber: "",
        amount: "",
        description: "",
        beneficiaryName: "",
        beneficiaryBank: "",
        beneficiaryBankCode: "",
        pin: "",
      });
      setRecipientName("");
    } catch (error) {
      console.error("Transfer error:", error);
      setSnackbarMessage(error.message || "Transfer failed. Please try again.");
      setSnackbarType("error");
      setSnackbarVisible(true);
    } finally {
      setSubmitting(false);
    }
  };

  const selectedSource =
    sourceAccounts.find((a) => a.account_number === selectedSourceAccountNumber) || account;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      <ScrollView style={styles.scrollView}>
        {loading ? (
          <Card style={styles.card}>
            <Card.Content style={styles.loadingContainer}>
              <ActivityIndicator size="large" />
              <Text style={styles.loadingText}>Loading account...</Text>
            </Card.Content>
          </Card>
        ) : (
          <>
            {/* Account Balance Card */}
            {account && (
              <Card style={styles.balanceCard}>
                <Card.Content>
                  <Text variant="labelMedium" style={styles.balanceLabel}>
                    Your Account
                  </Text>
                  <Text variant="bodyMedium" style={styles.accountNumber}>
                    {account.account_number}
                  </Text>
                  <Text variant="headlineMedium" style={styles.balance}>
                    ₦{parseFloat(account.balance || account.available_balance || 0).toLocaleString()}
                  </Text>
                </Card.Content>
              </Card>
            )}

            {/* Source Account Picker */}
            <Card style={styles.card}>
              <Card.Content>
                <Text variant="titleSmall" style={styles.sectionLabel}>
                  Source Account
                </Text>
                {isLoadingSourceAccounts ? (
                  <ActivityIndicator style={{ marginTop: spacing.sm }} />
                ) : sourceAccounts.length === 0 ? (
                  <View style={styles.singleAccountRow}>
                    <Icon name="bank" size={20} color={colors.primary} />
                    <Text variant="bodyMedium" style={styles.singleAccountText}>
                      {account?.account_name || account?.full_name || "Agent Account"} •{" "}
                      {account?.account_number} • NGN
                    </Text>
                  </View>
                ) : (
                  sourceAccounts.map((item) => {
                    const isSelected = selectedSourceAccountNumber === item.account_number;
                    const typeIcon =
                      item.owner_type === "store" ? "store" :
                      item.owner_type === "business" ? "briefcase" : "account";
                    return (
                      <TouchableOpacity
                        key={item.account_number}
                        onPress={() => setSelectedSourceAccountNumber(item.account_number)}
                        style={[
                          styles.accountOption,
                          isSelected && { borderColor: colors.primary, backgroundColor: colors.primary + "10" },
                        ]}
                      >
                        <View style={[styles.accountTypeIcon, isSelected && { backgroundColor: colors.primary + "20" }]}>
                          <Icon name={typeIcon} size={18} color={isSelected ? colors.primary : "#6B7280"} />
                        </View>
                        <View style={styles.accountOptionInfo}>
                          <Text variant="bodyMedium" style={styles.accountOptionName}>
                            {item.display_name}
                          </Text>
                          <Text variant="bodySmall" style={styles.accountOptionNumber}>
                            {item.account_number} • {item.account_currency || item.currency || "NGN"} •{" "}
                            ₦{parseFloat(item.balance || item.available_balance || 0).toLocaleString()}
                          </Text>
                        </View>
                        {isSelected && (
                          <Icon name="check-circle" size={18} color={colors.primary} />
                        )}
                      </TouchableOpacity>
                    );
                  })
                )}
              </Card.Content>
            </Card>

            {/* Transfer Form */}
            <Card style={styles.card}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.cardTitle}>
                  Transfer Money
                </Text>

                <SegmentedButtons
                  value={transferType}
                  onValueChange={(v) => {
                    setTransferType(v);
                    setRecipientName("");
                    setLookupError("");
                  }}
                  buttons={[
                    { value: "inbound", label: "Inbound" },
                    { value: "outbound", label: "Outbound" },
                  ]}
                  style={styles.segmentedButtons}
                />

                <Text variant="bodySmall" style={styles.helperText}>
                  {transferType === "inbound"
                    ? "Transfer between agent accounts"
                    : "Transfer to external bank accounts"}
                </Text>

                {/* Recipient Account Number with auto-lookup */}
                <TextInput
                  label="Recipient Account Number"
                  value={formData.recipientAccountNumber}
                  onChangeText={(value) => {
                    const digits = value.replace(/\D/g, "").slice(0, 10);
                    setFormData((prev) => ({ ...prev, recipientAccountNumber: digits }));
                  }}
                  mode="outlined"
                  style={styles.input}
                  placeholder="Enter 10-digit account number"
                  keyboardType="numeric"
                  maxLength={10}
                  left={<TextInput.Icon icon="account" />}
                  right={
                    isLookingUp
                      ? <TextInput.Icon icon={() => <ActivityIndicator size={16} />} />
                      : recipientName
                        ? <TextInput.Icon icon="check-circle" color="#10B981" />
                        : null
                  }
                  disabled={submitting}
                />

                {/* Lookup result */}
                {recipientName ? (
                  <View style={styles.recipientConfirm}>
                    <Icon name="account-check" size={18} color="#10B981" />
                    <Text variant="bodyMedium" style={styles.recipientName}>
                      {recipientName}
                    </Text>
                  </View>
                ) : lookupError ? (
                  <View style={styles.recipientError}>
                    <Icon name="alert-circle-outline" size={16} color="#EF4444" />
                    <Text variant="bodySmall" style={styles.recipientErrorText}>
                      {lookupError}
                    </Text>
                  </View>
                ) : formData.recipientAccountNumber.length > 0 &&
                  formData.recipientAccountNumber.length < 10 ? (
                  <Text variant="bodySmall" style={styles.digitCount}>
                    {formData.recipientAccountNumber.length}/10 digits
                  </Text>
                ) : null}

                <Divider style={styles.divider} />

                <TextInput
                  label="Amount"
                  value={formData.amount}
                  onChangeText={(value) =>
                    setFormData((prev) => ({ ...prev, amount: value }))
                  }
                  mode="outlined"
                  keyboardType="numeric"
                  style={styles.input}
                  placeholder="0.00"
                  left={<TextInput.Icon icon="currency-ngn" />}
                  disabled={submitting}
                />

                {transferType === "outbound" && (
                  <>
                    <TextInput
                      label="Beneficiary Name"
                      value={formData.beneficiaryName}
                      onChangeText={(value) =>
                        setFormData((prev) => ({ ...prev, beneficiaryName: value }))
                      }
                      mode="outlined"
                      style={styles.input}
                      placeholder="Enter beneficiary name"
                      left={<TextInput.Icon icon="account" />}
                      disabled={submitting}
                    />

                    {/* Bank picker */}
                    {isLoadingBanks ? (
                      <ActivityIndicator style={{ marginBottom: spacing.md }} />
                    ) : (
                      <TextInput
                        label="Bank Code"
                        value={formData.beneficiaryBankCode}
                        onChangeText={(value) =>
                          setFormData((prev) => ({ ...prev, beneficiaryBankCode: value }))
                        }
                        mode="outlined"
                        style={styles.input}
                        placeholder="e.g. 058"
                        keyboardType="numeric"
                        left={<TextInput.Icon icon="bank" />}
                        disabled={submitting}
                      />
                    )}

                    {!!formData.beneficiaryBankCode && banks.length > 0 && (
                      <Text style={styles.bankName}>
                        {banks.find(
                          (b) => String(b.code) === String(formData.beneficiaryBankCode),
                        )?.name || "Unknown bank"}
                      </Text>
                    )}
                  </>
                )}

                <TextInput
                  label="Description (Optional)"
                  value={formData.description}
                  onChangeText={(value) =>
                    setFormData((prev) => ({ ...prev, description: value }))
                  }
                  mode="outlined"
                  style={styles.input}
                  multiline
                  numberOfLines={2}
                  placeholder="Add a note"
                  left={<TextInput.Icon icon="text" />}
                  disabled={submitting}
                />

                <TextInput
                  label="PIN"
                  value={formData.pin}
                  onChangeText={(value) =>
                    setFormData((prev) => ({ ...prev, pin: value }))
                  }
                  mode="outlined"
                  style={styles.input}
                  placeholder="Enter 4-digit PIN"
                  keyboardType="numeric"
                  secureTextEntry
                  maxLength={4}
                  left={<TextInput.Icon icon="lock" />}
                  disabled={submitting}
                />

                {/* Transfer summary before submit */}
                {recipientName && formData.amount ? (
                  <View style={styles.summaryBox}>
                    <Text variant="bodySmall" style={styles.summaryLabel}>
                      Transfer Summary
                    </Text>
                    <View style={styles.summaryRow}>
                      <Text variant="bodySmall" style={styles.summaryKey}>From</Text>
                      <Text variant="bodySmall" style={styles.summaryValue}>
                        {selectedSource?.account_number}
                      </Text>
                    </View>
                    <View style={styles.summaryRow}>
                      <Text variant="bodySmall" style={styles.summaryKey}>To</Text>
                      <Text variant="bodySmall" style={styles.summaryValue}>
                        {recipientName} ({formData.recipientAccountNumber})
                      </Text>
                    </View>
                    <View style={styles.summaryRow}>
                      <Text variant="bodySmall" style={styles.summaryKey}>Amount</Text>
                      <Text variant="bodyMedium" style={styles.summaryAmount}>
                        ₦{parseFloat(formData.amount || 0).toLocaleString()}
                      </Text>
                    </View>
                  </View>
                ) : null}

                <Button
                  mode="contained"
                  onPress={handleTransfer}
                  disabled={
                    submitting ||
                    !formData.recipientAccountNumber ||
                    !formData.amount ||
                    lookupError !== ""
                  }
                  loading={submitting}
                  style={styles.submitButton}
                >
                  {submitting
                    ? "Processing..."
                    : `Transfer ₦${parseFloat(formData.amount || 0).toLocaleString()}`}
                </Button>
              </Card.Content>
            </Card>
          </>
        )}
      </ScrollView>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={3000}
        style={[
          styles.snackbar,
          snackbarType === "error" && styles.snackbarError,
        ]}
      >
        {snackbarMessage}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  scrollView: { flex: 1 },
  balanceCard: {
    margin: spacing.md,
    marginBottom: 0,
    backgroundColor: colors.primary,
  },
  card: {
    margin: spacing.md,
    marginTop: spacing.sm,
  },
  cardTitle: {
    fontWeight: "bold",
    marginBottom: spacing.md,
  },
  sectionLabel: {
    color: "#6B7280",
    marginBottom: spacing.sm,
    fontWeight: "600",
  },
  loadingContainer: {
    alignItems: "center",
    padding: spacing.lg,
  },
  loadingText: {
    marginTop: spacing.md,
    color: "#666",
  },
  balanceLabel: {
    color: "#fff",
    opacity: 0.85,
    marginBottom: spacing.xs,
  },
  accountNumber: {
    fontSize: 13,
    marginBottom: spacing.xs,
    color: "#fff",
    opacity: 0.8,
  },
  balance: {
    fontWeight: "bold",
    color: "#fff",
  },
  singleAccountRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  singleAccountText: {
    color: "#374151",
    flex: 1,
  },
  accountOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    marginBottom: spacing.sm,
  },
  accountTypeIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
  },
  accountOptionInfo: { flex: 1 },
  accountOptionName: {
    fontWeight: "600",
    color: "#111827",
  },
  accountOptionNumber: {
    color: "#6B7280",
    marginTop: 2,
  },
  segmentedButtons: { marginBottom: spacing.sm },
  helperText: {
    color: "#6B7280",
    marginBottom: spacing.md,
    fontStyle: "italic",
  },
  input: { marginBottom: spacing.sm },
  divider: { marginBottom: spacing.md },
  recipientConfirm: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#ECFDF5",
    borderRadius: 8,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    marginTop: -spacing.xs,
  },
  recipientName: {
    color: "#065F46",
    fontWeight: "600",
    flex: 1,
  },
  recipientError: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.sm,
    marginTop: -spacing.xs,
  },
  recipientErrorText: {
    color: "#EF4444",
  },
  digitCount: {
    color: "#9CA3AF",
    marginBottom: spacing.sm,
    marginTop: -spacing.xs,
  },
  bankName: {
    color: "#374151",
    marginBottom: spacing.md,
    fontStyle: "italic",
    fontSize: 13,
  },
  summaryBox: {
    backgroundColor: "#F3F4F6",
    borderRadius: 10,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  summaryLabel: {
    fontWeight: "700",
    color: "#374151",
    marginBottom: spacing.sm,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  summaryKey: { color: "#6B7280" },
  summaryValue: { color: "#111827", flex: 1, textAlign: "right" },
  summaryAmount: {
    color: "#10B981",
    fontWeight: "700",
  },
  submitButton: {
    marginTop: spacing.sm,
    paddingVertical: spacing.xs,
  },
  snackbar: { backgroundColor: "#2E7D32" },
  snackbarError: { backgroundColor: "#D32F2F" },
});

export { TransferScreen };
