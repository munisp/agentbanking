import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import {
  Button,
  Card,
  Snackbar,
  Text,
  TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { disputeApi } from "../../services/apiService";
import { spacing } from "../../theme";
const DISPUTE_REASONS = [
  { key: "wrong_amount", label: "Wrong Amount", icon: "currency-usd-off" },
  { key: "wrong_account", label: "Wrong Account", icon: "account-alert" },
  { key: "duplicate_transaction", label: "Duplicate Transaction", icon: "content-copy" },
  { key: "unauthorized", label: "Unauthorized Transaction", icon: "shield-alert" },
  { key: "failed_credit", label: "Failed Credit", icon: "bank-off" },
  { key: "technical_error", label: "Technical Error", icon: "wrench" },
  { key: "other", label: "Other", icon: "dots-horizontal-circle" },
];

export default function CreateDisputeScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [transactionRef, setTransactionRef] = useState("");
  const [selectedReason, setSelectedReason] = useState(null);
  const [description, setDescription] = useState("");
  const [evidence, setEvidence] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [disputeId, setDisputeId] = useState(null);

  const handleSubmit = async () => {
    if (!transactionRef.trim()) {
      setError("Please enter a transaction reference");
      return;
    }
    if (!selectedReason) {
      setError("Please select a reason for the dispute");
      return;
    }
    if (description.trim().length < 10) {
      setError("Description must be at least 10 characters");
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        transaction_reference: transactionRef.trim(),
        reason: selectedReason,
        description: description.trim(),
        ...(evidence.trim() && { evidence: evidence.trim() }),
      };

      const response = await disputeApi.createDispute(payload);
      const newDisputeId =
        response?.dispute_id ||
        response?.id ||
        response?.data?.dispute_id ||
        `DSP-${Date.now()}`;
      setDisputeId(newDisputeId);
      setSubmitted(true);
    } catch (err) {
      setError(err.message || "Failed to submit dispute");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <View style={styles.successContainer}>
        <Icon name="shield-check" size={72} color="#10B981" />
        <Text variant="headlineSmall" style={styles.successTitle}>
          Dispute Filed Successfully
        </Text>
        <Text variant="bodyMedium" style={styles.successSubtitle}>
          Your dispute has been logged and will be reviewed within 2–3 business days.
        </Text>
        {disputeId && (
          <Card style={styles.refCard}>
            <Card.Content>
              <Text variant="bodySmall" style={{ color: "#6B7280", textAlign: "center" }}>
                Dispute Reference
              </Text>
              <Text variant="titleMedium" style={styles.refText}>
                {disputeId}
              </Text>
            </Card.Content>
          </Card>
        )}
        <Button
          mode="contained"
          onPress={() => navigation.navigate("Disputes")}
          style={styles.doneButton}
          buttoncolor={colors.primary}
        >
          View My Disputes
        </Button>
        <Button
          mode="outlined"
          onPress={() => navigation.goBack()}
          style={[styles.doneButton, { marginTop: spacing.sm }]}
        >
          Go Back
        </Button>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
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
              left={<TextInput.Icon icon="identifier" />}
              style={styles.input}
            />
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Reason for Dispute
            </Text>
            <View style={styles.reasonGrid}>
              {DISPUTE_REASONS.map((r) => (
                <View key={r.key} style={styles.reasonItemWrapper}>
                  <View
                    onTouchEnd={() => setSelectedReason(r.key)}
                    style={[
                      styles.reasonItem,
                      selectedReason === r.key && styles.reasonItemSelected,
                    ]}
                  >
                    <Icon
                      name={r.icon}
                      size={22}
                      color={selectedReason === r.key ? colors.primary : "#9CA3AF"}
                    />
                    <Text
                      variant="bodySmall"
                      style={[
                        styles.reasonLabel,
                        selectedReason === r.key && styles.reasonLabelSelected,
                      ]}
                    >
                      {r.label}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Description <Text style={styles.required}>*</Text>
            </Text>
            <TextInput
              mode="outlined"
              placeholder="Describe the issue in detail (min 10 characters)"
              value={description}
              onChangeText={setDescription}
              multiline
              numberOfLines={4}
              style={[styles.input, styles.textArea]}
            />
            <Text variant="bodySmall" style={styles.charCount}>
              {description.length} characters
            </Text>
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Evidence <Text style={styles.optional}>(optional)</Text>
            </Text>
            <TextInput
              mode="outlined"
              placeholder="Add any relevant evidence (receipt number, screenshot URL, etc.)"
              value={evidence}
              onChangeText={setEvidence}
              multiline
              numberOfLines={3}
              style={[styles.input, styles.textArea]}
            />
          </Card.Content>
        </Card>

        <View style={styles.submitContainer}>
          <Button
            mode="contained"
            onPress={handleSubmit}
            loading={submitting}
            disabled={submitting}
            icon="send"
            buttoncolor={colors.primary}
            style={styles.submitButton}
          >
            Submit Dispute
          </Button>
          <Button
            mode="outlined"
            onPress={() => navigation.goBack()}
            style={styles.cancelButton}
          >
            Cancel
          </Button>
        </View>
      </ScrollView>

      <Snackbar visible={!!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  scroll: { flex: 1 },
  card: { margin: spacing.md, marginBottom: 0 },
  sectionTitle: { fontWeight: "700", color: "#111827", marginBottom: spacing.sm },
  input: { backgroundColor: "#fff" },
  textArea: { height: undefined, minHeight: 80 },
  charCount: { color: "#9CA3AF", textAlign: "right", marginTop: 4 },
  reasonGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  reasonItemWrapper: { width: "46%" },
  reasonItem: {
    borderWidth: 1.5,
    borderColor: "#E5E7EB",
    borderRadius: 8,
    padding: spacing.sm,
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#fff",
  },
  reasonItemSelected: {
    borderColor: colors.primary,
    backgroundColor: "#E0F2F7",
  },
  reasonLabel: {
    fontSize: 11,
    color: "#6B7280",
    textAlign: "center",
  },
  reasonLabelSelected: { color: colors.primary, fontWeight: "600" },
  required: { color: "#EF4444" },
  optional: { color: "#9CA3AF", fontWeight: "400", fontSize: 12 },
  submitContainer: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xl,
  },
  submitButton: { borderRadius: 8 },
  cancelButton: { borderRadius: 8 },
  successContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: "#F9FAFB",
  },
  successTitle: { fontWeight: "700", marginTop: spacing.lg, color: "#111827", textAlign: "center" },
  successSubtitle: { color: "#6B7280", marginTop: spacing.sm, textAlign: "center", lineHeight: 22 },
  refCard: { marginTop: spacing.lg, width: "80%" },
  refText: { fontWeight: "700", textAlign: "center", color: colors.primary, marginTop: spacing.xs },
  doneButton: { marginTop: spacing.lg, width: "100%", borderRadius: 8 },
});
