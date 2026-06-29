import * as SecureStore from "expo-secure-store";
import React, { useState } from "react";
import { ScrollView, StyleSheet } from "react-native";
import { Button, Card, Snackbar, Text, TextInput, useTheme} from "react-native-paper";
import { remittanceApi } from "../../services/apiService";

export default function RemittanceVerificationScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [transactionReference, setTransactionReference] = useState("");
  const [disburseCode, setDisburseCode] = useState("");
  const [transactionDetails, setTransactionDetails] = useState(null);
  const [verificationStatus, setVerificationStatus] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [disbursing, setDisbursing] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [snackbar, setSnackbar] = useState({ visible: false, text: "", error: false });

  const verify = async () => {
    if (!transactionReference || !disburseCode) {
      setSnackbar({ visible: true, text: "Transaction reference and disburse code are required", error: true });
      return;
    }

    setVerifying(true);
    setErrorMessage("");
    setSuccessMessage("");
    setVerificationStatus(null);
    try {
      const data = await remittanceApi.verifyTransaction({
        transaction_reference: transactionReference,
        disburse_code: disburseCode,
      });

      setTransactionDetails(data.data);
      setVerificationStatus("verified");
      setSuccessMessage(data.message || "Transaction verified successfully!");
      setSnackbar({ visible: true, text: data.message || "Transaction verified", error: false });
    } catch (error) {
      setVerificationStatus("failed");
      setErrorMessage(error?.message || "Verification failed");
      setSnackbar({ visible: true, text: error?.message || "Verification failed", error: true });
      setTransactionDetails(null);
    } finally {
      setVerifying(false);
    }
  };

  const markAsDisbursed = async () => {
    if (!transactionDetails?.transaction_id) return;

    setDisbursing(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const agentId = await SecureStore.getItemAsync("keycloakId");
      const data = await remittanceApi.markTransactionDisbursed(
        transactionDetails.transaction_id,
        {
          transaction_reference: transactionReference,
          disburse_code: disburseCode,
          agent_id: agentId,
        },
      );

      setVerificationStatus("disbursed");
      setSuccessMessage(data.message || "Transaction marked as disbursed successfully!");
      setTransactionDetails((prev) => ({
        ...prev,
        status: "disbursed",
        disbursed_at: new Date().toISOString(),
      }));
      setSnackbar({ visible: true, text: data.message || "Marked as disbursed", error: false });
    } catch (error) {
      setSnackbar({ visible: true, text: error?.message || "Failed to mark as disbursed", error: true });
    } finally {
      setDisbursing(false);
    }
  };

  const handleReset = () => {
    setTransactionReference("");
    setDisburseCode("");
    setTransactionDetails(null);
    setVerificationStatus(null);
    setSuccessMessage("");
    setErrorMessage("");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Remittance Transaction Verification</Text>
      <Text style={styles.subtitle}>Verify and disburse remittance transactions to customers</Text>

      <Card style={styles.card}>
        <Card.Title title="Verify Transaction" />
        <Card.Content>
          <TextInput
            label="Transaction Reference"
            value={transactionReference}
            onChangeText={setTransactionReference}
            mode="outlined"
            style={styles.input}
          />
          <TextInput
            label="Disburse Code"
            value={disburseCode}
            onChangeText={setDisburseCode}
            mode="outlined"
            keyboardType="number-pad"
            style={styles.input}
          />
          <Button mode="contained" loading={verifying} disabled={verifying} onPress={verify}>
            Verify
          </Button>
          <Button mode="outlined" onPress={handleReset} style={styles.secondaryBtn}>
            Reset
          </Button>

          {!!errorMessage && <Text style={styles.errorText}>{errorMessage}</Text>}
          {!!successMessage && verificationStatus === "verified" && (
            <Text style={styles.successText}>{successMessage}</Text>
          )}
          {!!successMessage && verificationStatus === "disbursed" && (
            <Text style={styles.infoText}>{successMessage}</Text>
          )}
        </Card.Content>
      </Card>

      {!transactionDetails && !verificationStatus && (
        <Card style={styles.card}>
          <Card.Title title="No Transaction Verified" />
          <Card.Content>
            <Text style={styles.placeholderText}>
              Enter the transaction reference and disburse code to verify and view transaction details.
            </Text>
          </Card.Content>
        </Card>
      )}

      {verificationStatus === "failed" && (
        <Card style={styles.card}>
          <Card.Title title="Verification Failed" />
          <Card.Content>
            <Text style={styles.placeholderText}>
              The transaction could not be verified. Please check your details and try again.
            </Text>
          </Card.Content>
        </Card>
      )}

      {transactionDetails && verificationStatus === "verified" && (
        <Card style={styles.card}>
          <Card.Title title="Transaction Verified" subtitle="Ready to disburse" />
          <Card.Content>
            <Text style={styles.amountLine}>
              {(transactionDetails.currency || "NGN") + " "}
              {parseFloat(transactionDetails.amount || 0).toLocaleString()}
            </Text>

            <Card style={styles.innerCard}>
              <Card.Content>
                <Text style={styles.sectionTitle}>Sender</Text>
                <Text>{transactionDetails.sender_name || "N/A"}</Text>
                <Text>{transactionDetails.sender_account || transactionDetails.sender_id || ""}</Text>
              </Card.Content>
            </Card>

            <Card style={styles.innerCard}>
              <Card.Content>
                <Text style={styles.sectionTitle}>Recipient</Text>
                <Text>{transactionDetails.recipient_name || "N/A"}</Text>
                <Text>{transactionDetails.recipient_account || transactionDetails.recipient_id || ""}</Text>
              </Card.Content>
            </Card>

            <Text>ID: {transactionDetails.transaction_id || transactionDetails.id || "-"}</Text>
            <Text>Reference: {transactionDetails.transaction_reference || transactionReference}</Text>
            <Text>Status: {transactionDetails.status || "Pending Disbursement"}</Text>
            <Text>
              Date: {transactionDetails.created_at ? new Date(transactionDetails.created_at).toLocaleString() : "N/A"}
            </Text>
            {!!transactionDetails.description && <Text>Description: {transactionDetails.description}</Text>}

            <Button
              mode="contained"
              loading={disbursing}
              disabled={disbursing || String(transactionDetails.status).toLowerCase() === "disbursed"}
              onPress={markAsDisbursed}
              style={styles.disburseBtn}
            >
              Mark as Disbursed
            </Button>
          </Card.Content>
        </Card>
      )}

      {transactionDetails && verificationStatus === "disbursed" && (
        <Card style={styles.card}>
          <Card.Title title="Transaction Disbursed" subtitle="Successfully completed" />
          <Card.Content>
            <Text style={styles.successText}>Disbursement Successful</Text>
            <Text style={styles.placeholderText}>
              The transaction has been marked as disbursed and the funds have been released to the recipient.
            </Text>

            <Text>Amount Disbursed: {(transactionDetails.currency || "NGN") + " "}{parseFloat(transactionDetails.amount || 0).toLocaleString()}</Text>
            <Text>Recipient: {transactionDetails.recipient_name || "N/A"}</Text>
            <Text>Transaction Reference: {transactionReference}</Text>
            <Text>
              Disbursed At: {transactionDetails.disbursed_at ? new Date(transactionDetails.disbursed_at).toLocaleString() : new Date().toLocaleString()}
            </Text>

            <Button mode="contained" onPress={handleReset} style={styles.disburseBtn}>
              Verify Another Transaction
            </Button>
          </Card.Content>
        </Card>
      )}

      <Card style={styles.card}>
        <Card.Content>
          <Text style={styles.sectionTitle}>Quick Verification</Text>
          <Text style={styles.placeholderText}>
            Verify transactions in seconds using the transaction reference and disburse code.
          </Text>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Text style={styles.sectionTitle}>Secure Process</Text>
          <Text style={styles.placeholderText}>
            All transactions require verification codes for added security.
          </Text>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Text style={styles.sectionTitle}>Instant Disbursement</Text>
          <Text style={styles.placeholderText}>
            Funds are released immediately upon successful verification.
          </Text>
        </Card.Content>
      </Card>

      <Snackbar
        visible={snackbar.visible}
        onDismiss={() => setSnackbar((prev) => ({ ...prev, visible: false }))}
        duration={3000}
        style={{ backgroundColor: snackbar.error ? "#DC2626" : "#16A34A" }}
      >
        {snackbar.text}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F3F4F6" },
  content: { padding: 16, gap: 12 },
  title: { fontSize: 24, fontWeight: "700", marginBottom: 8 },
  subtitle: { color: "#4B5563", marginTop: -6, marginBottom: 6 },
  card: { borderRadius: 12 },
  input: { marginBottom: 8 },
  disburseBtn: { marginTop: 10 },
  secondaryBtn: { marginTop: 8 },
  errorText: { color: "#B91C1C", marginTop: 8 },
  successText: { color: "#166534", marginTop: 8, fontWeight: "700" },
  infoText: { color: "#1D4ED8", marginTop: 8, fontWeight: "700" },
  placeholderText: { color: "#4B5563" },
  amountLine: { fontSize: 28, fontWeight: "700", marginBottom: 10 },
  innerCard: { marginBottom: 8, borderRadius: 10, backgroundColor: "#F9FAFB" },
  sectionTitle: { fontWeight: "700", marginBottom: 4 },
});
