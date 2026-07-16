import React, { useState } from "react";
import {
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
  Divider,
  Snackbar,
  Text,
  TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { ledgerApi, reversalApi } from "../../services/apiService";
import { spacing } from "../../theme";
const lookupCache = new Map();

const REVERSAL_REASONS = [
  { key: "customer_request", label: "Customer Request", icon: "account-cancel" },
  { key: "wrong_amount", label: "Wrong Amount", icon: "currency-usd-off" },
  { key: "wrong_account", label: "Wrong Account", icon: "account-alert" },
  { key: "technical_error", label: "Technical Error", icon: "wrench" },
  { key: "duplicate_transaction", label: "Duplicate Transaction", icon: "content-copy" },
];

const STEPS = { ENTER_REF: 0, CONFIRM: 1, SUCCESS: 2 };

export default function ReversalScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [step, setStep] = useState(STEPS.ENTER_REF);
  const [transactionRef, setTransactionRef] = useState("");
  const [looking, setLooking] = useState(false);
  const [transaction, setTransaction] = useState(null);
  const [selectedReason, setSelectedReason] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [reversalRef, setReversalRef] = useState(null);
  const [error, setError] = useState("");

  const handleLookup = async () => {
    const normalizedRef = transactionRef.trim().toUpperCase();
    if (!normalizedRef) {
      setError("Please enter a transaction reference");
      return;
    }
    try {
      setLooking(true);
      setError("");

      const cachedTransaction = lookupCache.get(normalizedRef);
      if (cachedTransaction) {
        setTransaction(cachedTransaction);
        setStep(STEPS.CONFIRM);
        return;
      }

      let txn = null;
      try {
        txn = await reversalApi.lookupTransaction(normalizedRef);
      } catch {
        // Fallback for environments where the reference endpoint resolves via generic transaction lookup.
        txn = await ledgerApi.getTransaction(normalizedRef);
      }

      const resolvedTransaction = txn?.transaction || txn;
      if (!resolvedTransaction) throw new Error("Transaction not found");

      lookupCache.set(normalizedRef, resolvedTransaction);
      setTransaction(resolvedTransaction);
      setStep(STEPS.CONFIRM);
    } catch (err) {
      setError(err.message || "Transaction not found. Please check the reference.");
    } finally {
      setLooking(false);
    }
  };

  const handleReversal = async () => {
    if (!selectedReason) {
      setError("Please select a reason for the reversal");
      return;
    }
    try {
      setSubmitting(true);
      setError("");
      const response = await reversalApi.initiateReversal({
        transaction_reference: transactionRef.trim().toUpperCase(),
        reason: selectedReason,
        transaction_id: transaction?.id || transaction?.transaction_id,
      });
      const ref =
        response?.reversal_reference ||
        response?.reference ||
        response?.data?.reference ||
        `REV-${Date.now()}`;
      setReversalRef(ref);
      setStep(STEPS.SUCCESS);
    } catch (err) {
      setError(err.message || "Failed to initiate reversal");
    } finally {
      setSubmitting(false);
    }
  };

  const txnAmount = parseFloat(
    transaction?.amount || transaction?.debit || transaction?.credit || 0,
  );

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      {/* Step 0: Enter Reference */}
      {step === STEPS.ENTER_REF && (
        <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
          <View style={styles.iconContainer}>
            <View style={styles.iconCircle}>
              <Icon name="undo-variant" size={40} color={colors.primary} />
            </View>
            <Text variant="titleLarge" style={styles.pageTitle}>
              Transaction Reversal
            </Text>
            <Text variant="bodyMedium" style={styles.pageSubtitle}>
              Enter the transaction reference to look it up and initiate a reversal.
            </Text>
          </View>

          <Card style={styles.card}>
            <Card.Content>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                Transaction Reference
              </Text>
              <TextInput
                mode="outlined"
                placeholder="e.g. TXN-20250421-001"
                value={transactionRef}
                onChangeText={setTransactionRef}
                autoCapitalize="characters"
                left={<TextInput.Icon icon="magnify" />}
                style={styles.input}
                onSubmitEditing={handleLookup}
                returnKeyType="search"
              />
            </Card.Content>
          </Card>

          <View style={styles.actionContainer}>
            <Button
              mode="contained"
              onPress={handleLookup}
              loading={looking}
              disabled={looking}
              icon="magnify"
              buttoncolor={colors.primary}
              style={styles.btn}
            >
              Look Up Transaction
            </Button>
          </View>
        </ScrollView>
      )}

      {/* Step 1: Confirm & Select Reason */}
      {step === STEPS.CONFIRM && transaction && (
        <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
          {/* Transaction Details */}
          <Card style={styles.card}>
            <Card.Content>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                Transaction Details
              </Text>
              {[
                { label: "Reference", value: transaction.reference || transactionRef },
                {
                  label: "Type",
                  value: transaction.transaction_type || transaction.type || "Transaction",
                },
                {
                  label: "Amount",
                  value: `₦${txnAmount.toLocaleString()}`,
                  style: { color: "#EF4444", fontWeight: "700" },
                },
                {
                  label: "Customer",
                  value:
                    transaction.customer_name ||
                    transaction.beneficiary_name ||
                    transaction.account_name ||
                    "—",
                },
                {
                  label: "Date",
                  value: transaction.created_at
                    ? new Date(transaction.created_at).toLocaleString()
                    : "—",
                },
                {
                  label: "Status",
                  value: transaction.status || "completed",
                  style: { color: "#10B981" },
                },
              ].map((item, i) => (
                <View key={item.label}>
                  <View style={styles.detailRow}>
                    <Text variant="bodySmall" style={styles.detailLabel}>
                      {item.label}
                    </Text>
                    <Text
                      variant="bodyMedium"
                      style={[styles.detailValue, item.style]}
                    >
                      {item.value}
                    </Text>
                  </View>
                  {i < 5 && <Divider style={styles.divider} />}
                </View>
              ))}
            </Card.Content>
          </Card>

          {/* Reason Selection */}
          <Card style={styles.card}>
            <Card.Content>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                Reason for Reversal
              </Text>
              {REVERSAL_REASONS.map((r) => (
                <View
                  key={r.key}
                  onTouchEnd={() => setSelectedReason(r.key)}
                  style={[
                    styles.reasonRow,
                    selectedReason === r.key && styles.reasonRowSelected,
                  ]}
                >
                  <Icon
                    name={r.icon}
                    size={20}
                    color={selectedReason === r.key ? colors.primary : "#9CA3AF"}
                  />
                  <Text
                    variant="bodyMedium"
                    style={[
                      styles.reasonText,
                      selectedReason === r.key && styles.reasonTextSelected,
                    ]}
                  >
                    {r.label}
                  </Text>
                  {selectedReason === r.key && (
                    <Icon name="check-circle" size={18} color={colors.primary} />
                  )}
                </View>
              ))}
            </Card.Content>
          </Card>

          <View style={styles.actionContainer}>
            <Button
              mode="contained"
              onPress={handleReversal}
              loading={submitting}
              disabled={submitting}
              icon="undo-variant"
              buttonColor="#EF4444"
              style={styles.btn}
            >
              Initiate Reversal
            </Button>
            <Button
              mode="outlined"
              onPress={() => {
                setStep(STEPS.ENTER_REF);
                setTransaction(null);
                setSelectedReason(null);
              }}
              style={styles.btn}
            >
              Change Reference
            </Button>
          </View>
        </ScrollView>
      )}

      {/* Step 2: Success */}
      {step === STEPS.SUCCESS && (
        <View style={styles.successContainer}>
          <Icon name="check-circle" size={72} color="#10B981" />
          <Text variant="headlineSmall" style={styles.successTitle}>
            Reversal Initiated - Funds will be returned within 24 hours
          </Text>
          {reversalRef && (
            <Card style={styles.refCard}>
              <Card.Content>
                <Text
                  variant="bodySmall"
                  style={{ color: "#6B7280", textAlign: "center" }}
                >
                  Reversal Reference
                </Text>
                <Text variant="titleMedium" style={styles.refText}>
                  {reversalRef}
                </Text>
              </Card.Content>
            </Card>
          )}
          <Button
            mode="contained"
            onPress={() => navigation.goBack()}
            style={styles.doneBtn}
            buttoncolor={colors.primary}
          >
            Done
          </Button>
        </View>
      )}

      <Snackbar visible={!!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  scroll: { flex: 1 },
  iconContainer: {
    alignItems: "center",
    padding: spacing.xl,
    paddingBottom: spacing.md,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#EEF2FF",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  pageTitle: { fontWeight: "700", color: "#111827", textAlign: "center" },
  pageSubtitle: { color: "#6B7280", textAlign: "center", marginTop: spacing.xs, lineHeight: 22 },
  card: { margin: spacing.md, marginBottom: 0 },
  sectionTitle: { fontWeight: "700", color: "#111827", marginBottom: spacing.sm },
  input: { backgroundColor: "#fff" },
  actionContainer: { padding: spacing.md, gap: spacing.sm },
  btn: { borderRadius: 8 },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  detailLabel: { color: "#6B7280" },
  detailValue: { fontWeight: "600", color: "#111827", textAlign: "right", flex: 1, marginLeft: spacing.md },
  divider: { backgroundColor: "#F3F4F6" },
  reasonRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: 8,
    marginBottom: spacing.xs,
    borderWidth: 1.5,
    borderColor: "transparent",
  },
  reasonRowSelected: {
    borderColor: colors.primary,
    backgroundColor: "#EEF2FF",
  },
  reasonText: { flex: 1, color: "#374151" },
  reasonTextSelected: { color: colors.primary, fontWeight: "600" },
  successContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  successTitle: { fontWeight: "700", marginTop: spacing.lg, color: "#111827", textAlign: "center" },
  successSubtitle: { color: "#6B7280", marginTop: spacing.sm, textAlign: "center" },
  refCard: { marginTop: spacing.lg, width: "80%" },
  refText: { fontWeight: "700", textAlign: "center", color: colors.primary, marginTop: spacing.xs },
  doneBtn: { marginTop: spacing.xl, width: "100%", borderRadius: 8 },
});
