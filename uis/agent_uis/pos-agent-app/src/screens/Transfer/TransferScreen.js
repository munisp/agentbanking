import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    Alert,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    ActivityIndicator,
    Button,
    Card,
    SegmentedButtons,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import { accountApi } from "../../services/apiService";
import transactionService from "../../services/transactionService";
import { spacing } from "../../theme";

export default function TransferScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [transferType, setTransferType] = useState("inbound");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [account, setAccount] = useState(null);
  const [sourceAccounts, setSourceAccounts] = useState([]);
  const [selectedSourceAccountNumber, setSelectedSourceAccountNumber] =
    useState("");
  const [isLoadingSourceAccounts, setIsLoadingSourceAccounts] = useState(false);
  const [sourceAccountLoadError, setSourceAccountLoadError] = useState("");
  const [banks, setBanks] = useState([]);
  const [isLoadingBanks, setIsLoadingBanks] = useState(false);
  const [bankLoadError, setBankLoadError] = useState("");
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarType, setSnackbarType] = useState("success");

  const [formData, setFormData] = useState({
    recipientAccountNumber: "",
    amount: "",
    description: "",
    beneficiaryName: "",
    beneficiaryBank: "",
    beneficiaryBankCode: "",
    pin: "",
  });

  // Fetch agent's account on mount
  useEffect(() => {
    fetchAgentAccount();
    loadSourceAccounts();
    loadBanks();
  }, []);

  const loadSourceAccounts = async () => {
    try {
      setIsLoadingSourceAccounts(true);
      setSourceAccountLoadError("");
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) return;

      const response = await accountApi.getAccounts(keycloakId);
      const accountList = Array.isArray(response)
        ? response
        : response?.account
          ? Array.isArray(response.account)
            ? response.account
            : [response.account]
          : [];
      const eligible = accountList.filter(
        (acc) =>
          String(acc?.status || "").toLowerCase() === "active" &&
          ["primary", "savings", "current", "mint"].includes(
            String(acc?.account_type || "").toLowerCase(),
          ) &&
          acc?.account_number,
      );
      setSourceAccounts(eligible);
      if (eligible.length > 0) {
        setSelectedSourceAccountNumber(eligible[0].account_number);
      }
    } catch (error) {
      console.error("Error loading source accounts:", error);
      setSourceAccountLoadError("Failed to load source accounts");
    } finally {
      setIsLoadingSourceAccounts(false);
    }
  };

  const loadBanks = async () => {
    try {
      setIsLoadingBanks(true);
      setBankLoadError("");
      const response = await accountApi.getBanks();
      const bankList =
        response?.banks || response?.data?.banks || response?.data || [];
      setBanks(Array.isArray(bankList) ? bankList : []);
    } catch (error) {
      console.error("Error loading banks:", error);
      setBankLoadError("Failed to load banks");
      setBanks([]);
    } finally {
      setIsLoadingBanks(false);
    }
  };

  const fetchAgentAccount = async () => {
    try {
      setLoading(true);
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      const response = await accountApi.getAccountByKeycloakId(keycloakId);
      // Handle if response is an array or object with account property
      const accountData = Array.isArray(response)
        ? response[0]
        : response?.account || response;

      setAccount(accountData);
    } catch (error) {
      console.error("Error fetching account:", error);
      Alert.alert("Error", "Failed to load your account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleTransfer = async () => {
    // Validate inputs
    const selectedSourceAccount =
      sourceAccounts.find(
        (item) => item.account_number === selectedSourceAccountNumber,
      ) || account;

    if (!selectedSourceAccount || !selectedSourceAccount.account_number) {
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
      if (!formData.beneficiaryBank.trim()) {
        Alert.alert("Error", "Please enter beneficiary bank");
        return;
      }
      if (!formData.beneficiaryBankCode.trim()) {
        Alert.alert("Error", "Please enter beneficiary bank code");
        return;
      }
    }

    try {
      setSubmitting(true);

      if (transferType === "inbound") {
        // Internal transfer between agents
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
        setSnackbarVisible(true);

        // Reset form
        setFormData({
          recipientAccountNumber: "",
          amount: "",
          description: "",
          beneficiaryName: "",
          beneficiaryBank: "",
          beneficiaryBankCode: "",
          pin: "",
        });
      } else {
        const selectedBank = banks.find(
          (bank) => String(bank.code) === String(formData.beneficiaryBankCode),
        );

        if (!selectedBank) {
          Alert.alert("Error", "Please select a valid bank code");
          return;
        }

        // External transfer to bank
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
        setSnackbarVisible(true);

        // Reset form
        setFormData({
          recipientAccountNumber: "",
          amount: "",
          description: "",
          beneficiaryName: "",
          beneficiaryBank: "",
          beneficiaryBankCode: "",
          pin: "",
        });
      }
    } catch (error) {
      console.error("Transfer error:", error);
      const errorMessage =
        error.message || "Transfer failed. Please try again.";
      setSnackbarMessage(errorMessage);
      setSnackbarType("error");
      setSnackbarVisible(true);
    } finally {
      setSubmitting(false);
    }
  };

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
              <Card style={styles.card}>
                <Card.Content>
                  <Text variant="labelMedium" style={styles.balanceLabel}>
                    Your Account
                  </Text>
                  <Text variant="bodyMedium" style={styles.accountNumber}>
                    {account.account_number}
                  </Text>
                  <Text variant="headlineMedium" style={styles.balance}>
                    ₦
                    {account.balance
                      ? parseFloat(account.balance).toLocaleString()
                      : "0.00"}
                  </Text>
                </Card.Content>
              </Card>
            )}

            <Card style={styles.card}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.cardTitle}>
                  Source Account
                </Text>
                {isLoadingSourceAccounts ? (
                  <ActivityIndicator />
                ) : sourceAccountLoadError ? (
                  <Text>{sourceAccountLoadError}</Text>
                ) : (
                  sourceAccounts.map((item) => (
                    <Button
                      key={item.account_number}
                      mode={
                        selectedSourceAccountNumber === item.account_number
                          ? "contained"
                          : "outlined"
                      }
                      onPress={() =>
                        setSelectedSourceAccountNumber(item.account_number)
                      }
                      style={styles.button}
                    >
                      {item.name} • {item.account_number} •{" "}
                      {item.account_currency}
                    </Button>
                  ))
                )}
              </Card.Content>
            </Card>

            {/* Transfer Form Card */}
            <Card style={styles.card}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.cardTitle}>
                  Transfer Money
                </Text>

                <SegmentedButtons
                  value={transferType}
                  onValueChange={setTransferType}
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

                <TextInput
                  label="Recipient Account Number"
                  value={formData.recipientAccountNumber}
                  onChangeText={(value) =>
                    setFormData((prev) => ({
                      ...prev,
                      recipientAccountNumber: value,
                    }))
                  }
                  mode="outlined"
                  style={styles.input}
                  placeholder="Enter account number"
                  keyboardType="numeric"
                  left={<TextInput.Icon icon="account" />}
                  disabled={submitting}
                />

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
                        setFormData((prev) => ({
                          ...prev,
                          beneficiaryName: value,
                        }))
                      }
                      mode="outlined"
                      style={styles.input}
                      placeholder="Enter beneficiary name"
                      left={<TextInput.Icon icon="account" />}
                      disabled={submitting}
                    />

                    <TextInput
                      label="Bank Name"
                      value={formData.beneficiaryBank}
                      onChangeText={(value) =>
                        setFormData((prev) => ({
                          ...prev,
                          beneficiaryBank: value,
                        }))
                      }
                      mode="outlined"
                      style={styles.input}
                      placeholder="Enter bank name"
                      left={<TextInput.Icon icon="bank" />}
                      disabled={submitting}
                    />

                    {isLoadingBanks ? (
                      <ActivityIndicator />
                    ) : bankLoadError ? (
                      <Text>{bankLoadError}</Text>
                    ) : null}

                    {/* <TextInput
                      label="Bank Code"
                      value={formData.beneficiaryBankCode}
                      onChangeText={(value) =>
                        setFormData((prev) => ({
                          ...prev,
                          beneficiaryBankCode: value,
                        }))
                      }
                      mode="outlined"
                      style={styles.input}
                      placeholder="Enter bank code (e.g., 058)"
                      keyboardType="numeric"
                      left={<TextInput.Icon icon="numeric" />}
                      disabled={submitting}
                    /> */}

                    {!!formData.beneficiaryBankCode && banks.length > 0 && (
                      <Text style={styles.helperText}>
                        {banks.find(
                          (bank) =>
                            String(bank.code) ===
                            String(formData.beneficiaryBankCode),
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
                  numberOfLines={3}
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

                <Button
                  mode="contained"
                  onPress={handleTransfer}
                  disabled={
                    submitting ||
                    !formData.recipientAccountNumber ||
                    !formData.amount
                  }
                  loading={submitting}
                  style={styles.button}
                >
                  {submitting
                    ? "Processing..."
                    : `Transfer ₦${formData.amount || "0"}`}
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
  scrollView: {
    flex: 1,
  },
  card: {
    margin: spacing.md,
  },
  cardTitle: {
    fontWeight: "bold",
    marginBottom: spacing.md,
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
    color: "#666",
    marginBottom: spacing.xs,
  },
  accountNumber: {
    fontSize: 14,
    marginBottom: spacing.sm,
    color: "#333",
  },
  balance: {
    fontWeight: "bold",
    color: "#2E7D32",
  },
  segmentedButtons: {
    marginBottom: spacing.sm,
  },
  helperText: {
    color: "#666",
    marginBottom: spacing.md,
    fontStyle: "italic",
  },
  input: {
    marginBottom: spacing.md,
  },
  button: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
  },
  snackbar: {
    backgroundColor: "#2E7D32",
  },
  snackbarError: {
    backgroundColor: "#D32F2F",
  },
  recentButton: {
    marginBottom: spacing.sm,
  },
});

export { TransferScreen };
