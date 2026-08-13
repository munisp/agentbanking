import * as SecureStore from "expo-secure-store";
import React, { useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import {
  Button,
  Card,
  SegmentedButtons,
  Snackbar,
  Text,
  TextInput, useTheme} from "react-native-paper";
import { accountApi, remittanceApi } from "../../services/apiService";

const SUPPORTED_CURRENCIES = {
  source: ["GBP", "USD", "EUR", "NGN", "GHS", "JPY", "AUD"],
  destination: ["NGN", "GHS", "USD", "GBP", "EUR", "JPY", "AUD"],
};

const CURRENCY_SYMBOLS = {
  GBP: "£",
  USD: "$",
  EUR: "€",
  NGN: "₦",
  GHS: "₵",
  JPY: "¥",
  AUD: "A$",
};

const DELIVERY_METHODS = {
  NGN: [
    { value: "bank_transfer", label: "Bank Transfer", time: "Instant - 30 mins" },
    { value: "mobile_money", label: "Mobile Money", time: "Instant" },
    { value: "cash_pickup", label: "Cash Pickup", time: "1 - 4 hours" },
  ],
  GHS: [
    { value: "bank_transfer", label: "Bank Transfer", time: "1 - 2 hours" },
    { value: "mobile_money", label: "Mobile Money", time: "Instant - 30 mins" },
    { value: "cash_pickup", label: "Cash Pickup", time: "2 - 6 hours" },
  ],
  default: [{ value: "bank_transfer", label: "Bank Transfer", time: "1 - 2 business days" }],
};

export default function SendRemittanceScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [step, setStep] = useState(1);
  const [recipientType, setRecipientType] = useState("bank");
  const [recipientAccount, setRecipientAccount] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [banks, setBanks] = useState([]);
  const [isLoadingBanks, setIsLoadingBanks] = useState(false);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [currency, setCurrency] = useState("NGN");
  const [destinationCurrency, setDestinationCurrency] = useState("NGN");
  const [deliveryMethod, setDeliveryMethod] = useState("bank_transfer");
  const [sourceAccounts, setSourceAccounts] = useState([]);
  const [sourceAccountNumber, setSourceAccountNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState({ visible: false, text: "", error: false });
  const [reference, setReference] = useState("");

  const sourceAccount = useMemo(
    () => sourceAccounts.find((item) => item.account_number === sourceAccountNumber),
    [sourceAccounts, sourceAccountNumber],
  );

  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState("");

  // Fetch the real exchange rate from the backend whenever the currency pair
  // changes. Rates and fees are NEVER fabricated locally.
  useEffect(() => {
    let cancelled = false;
    setQuote(null);
    setQuoteError("");
    if (!currency || !destinationCurrency) return;
    if (currency === destinationCurrency) {
      setQuote({ rate: 1 });
      return;
    }
    remittanceApi
      .getExchangeRate(currency, destinationCurrency)
      .then((data) => {
        if (cancelled) return;
        const rate = data?.data?.rate ?? data?.rate;
        if (typeof rate === "number") {
          setQuote({ rate });
        } else {
          setQuoteError("Exchange rate unavailable for this currency pair.");
        }
      })
      .catch((err) => {
        if (!cancelled) setQuoteError(err.message || "Could not fetch the exchange rate.");
      });
    return () => {
      cancelled = true;
    };
  }, [currency, destinationCurrency]);

  const exchangeRate = quote;

  // Indicative recipient amount before fees. The exact fees and final amount
  // are computed and confirmed by the server when the transfer is initiated.
  const receivedAmount = useMemo(() => {
    const parsedAmount = parseFloat(amount || "0");
    if (!parsedAmount || !exchangeRate?.rate) return "0.00";
    return (parsedAmount * exchangeRate.rate).toFixed(2);
  }, [amount, exchangeRate]);

  const deliveryMethods = DELIVERY_METHODS[destinationCurrency] || DELIVERY_METHODS.default;

  useEffect(() => {
    const loadSourceAccounts = async () => {
      try {
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
            acc?.account_number,
        );
        setSourceAccounts(eligible);
        if (eligible[0]?.account_number) {
          setSourceAccountNumber(eligible[0].account_number);
        }
      } catch (error) {
        setSnackbar({ visible: true, text: "Failed to load source accounts", error: true });
      }
    };

    const loadBanks = async () => {
      try {
        setIsLoadingBanks(true);
        const response = await accountApi.getBanks();
        const bankList = response?.banks || response?.data?.banks || response?.data || [];
        setBanks(Array.isArray(bankList) ? bankList : []);
      } catch (error) {
        setSnackbar({ visible: true, text: "Failed to load banks", error: true });
      } finally {
        setIsLoadingBanks(false);
      }
    };

    loadSourceAccounts();
    loadBanks();
  }, []);

  useEffect(() => {
    if (sourceAccount?.account_currency) {
      setCurrency(sourceAccount.account_currency);
    }
  }, [sourceAccount?.account_currency]);

  const isStepValid = (stepNum) => {
    if (stepNum === 1) {
      if (!sourceAccountNumber || !recipientName || !recipientAccount) return false;
      if (recipientType === "bank" && !bankCode) return false;
      return true;
    }
    if (stepNum === 2) {
      return Number(amount || 0) > 0;
    }
    return true;
  };

  const submit = async () => {
    if (!sourceAccountNumber || !recipientAccount || !amount) {
      setSnackbar({ visible: true, text: "Source account, recipient and amount are required", error: true });
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        switch_name: "mojaloop",
        amount: Number(amount || 0).toFixed(2),
        currency: String(currency || "NGN").toUpperCase(),
        to: {
          idType: "ACCOUNT_ID",
          idValue: recipientAccount,
          displayName: recipientName || "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: sourceAccountNumber,
          displayName: sourceAccount?.name || sourceAccount?.account_name || "Sender",
        },
        note: note || "Transfer",
      };

      const result = await remittanceApi.initiateTransfer(payload);

      const txnRef = result?.data?.reference || result?.reference || "N/A";
      setReference(txnRef);
      setSnackbar({ visible: true, text: `Remittance sent. Ref: ${txnRef}`, error: false });
    } catch (error) {
      setSnackbar({ visible: true, text: error?.message || "Failed to send remittance", error: true });
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinue = async () => {
    if (!isStepValid(step)) {
      setSnackbar({ visible: true, text: "Please complete required fields", error: true });
      return;
    }
    if (step < 3) {
      setStep((current) => current + 1);
      return;
    }
    await submit();
  };

  const handleReset = () => {
    setStep(1);
    setRecipientType("bank");
    setRecipientAccount("");
    setRecipientName("");
    setBankCode("");
    setAmount("");
    setNote("");
    setDestinationCurrency("NGN");
    setDeliveryMethod("bank_transfer");
    setReference("");
  };

  if (reference) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Card style={styles.card}>
          <Card.Title title="Transfer Successful!" subtitle="Remittance has been initiated" />
          <Card.Content>
            <Text style={styles.successRefLabel}>Transaction Reference</Text>
            <Text style={styles.successRef}>{reference}</Text>
            <View style={styles.successActions}>
              <Button mode="contained" onPress={handleReset}>Send Another Transfer</Button>
            </View>
          </Card.Content>
        </Card>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Send Remittance</Text>
      <Text style={styles.subtitle}>Send money internationally with competitive rates</Text>

      <View style={styles.stepperRow}>
        {[1, 2, 3].map((stepNum) => (
          <View key={stepNum} style={styles.stepItem}>
            <View style={[styles.stepCircle, step >= stepNum ? styles.stepCircleActive : styles.stepCircleInactive]}>
              <Text style={step >= stepNum ? styles.stepTextActive : styles.stepTextInactive}>{stepNum}</Text>
            </View>
            {stepNum < 3 ? <View style={[styles.stepLine, step > stepNum ? styles.stepLineActive : styles.stepLineInactive]} /> : null}
          </View>
        ))}
      </View>
      <View style={styles.stepLabels}>
        <Text style={styles.stepLabel}>Recipient</Text>
        <Text style={styles.stepLabel}>Amount</Text>
        <Text style={styles.stepLabel}>Review</Text>
      </View>

      <Card style={styles.card}>
        <Card.Title
          title={
            step === 1
              ? "Who are you sending to?"
              : step === 2
                ? "How much are you sending?"
                : "Review & Confirm"
          }
        />
        <Card.Content>
          {step === 1 && (
            <>
              <SegmentedButtons
                value={recipientType}
                onValueChange={setRecipientType}
                buttons={[
                  { value: "bank", label: "Bank" },
                  { value: "phone", label: "Phone" },
                  { value: "email", label: "Email" },
                ]}
                style={styles.input}
              />
              <TextInput
                label="Source Account"
                value={sourceAccountNumber}
                onChangeText={setSourceAccountNumber}
                mode="outlined"
                style={styles.input}
              />
              <TextInput
                label="Recipient Name"
                value={recipientName}
                onChangeText={setRecipientName}
                mode="outlined"
                style={styles.input}
              />
              <TextInput
                label={recipientType === "phone" ? "Phone Number" : recipientType === "email" ? "Email Address" : "Account Number"}
                value={recipientAccount}
                onChangeText={setRecipientAccount}
                mode="outlined"
                style={styles.input}
              />
              {recipientType === "bank" && (
                <TextInput
                  label={isLoadingBanks ? "Bank Code (loading...)" : "Bank Code"}
                  value={bankCode}
                  onChangeText={setBankCode}
                  mode="outlined"
                  style={styles.input}
                />
              )}
              <Text style={styles.sectionHint}>Sending to</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.currencyRow}>
                {SUPPORTED_CURRENCIES.destination.map((curr) => (
                  <Button
                    key={curr}
                    mode={destinationCurrency === curr ? "contained" : "outlined"}
                    compact
                    style={styles.currencyBtn}
                    onPress={() => setDestinationCurrency(curr)}
                  >
                    {curr}
                  </Button>
                ))}
              </ScrollView>
            </>
          )}

          {step === 2 && (
            <>
              <View style={styles.row}>
                <TextInput
                  label="You send"
                  value={amount}
                  onChangeText={setAmount}
                  mode="outlined"
                  keyboardType="numeric"
                  style={[styles.input, styles.flex]}
                />
                <TextInput
                  label="Currency"
                  value={currency}
                  onChangeText={setCurrency}
                  mode="outlined"
                  style={[styles.input, styles.currency]}
                />
              </View>

              {exchangeRate && (
                <Card style={styles.infoCard}>
                  <Card.Content>
                    <Text style={styles.infoTitle}>Exchange Rate</Text>
                    <Text style={styles.infoValue}>
                      1 {currency} = {exchangeRate.rate.toFixed(4)} {destinationCurrency}
                    </Text>
                  </Card.Content>
                </Card>
              )}

              {Number(amount || 0) > 0 && exchangeRate && (
                <Card style={styles.infoCard}>
                  <Card.Content>
                    <Text style={styles.infoTitle}>Recipient gets (indicative, before fees)</Text>
                    <Text style={styles.infoValue}>
                      {CURRENCY_SYMBOLS[destinationCurrency] || ""}
                      {receivedAmount}
                    </Text>
                  </Card.Content>
                </Card>
              )}

              {!!quoteError && (
                <Card style={styles.infoCard}>
                  <Card.Content>
                    <Text style={styles.infoTitle}>Exchange Rate</Text>
                    <Text>{quoteError}</Text>
                  </Card.Content>
                </Card>
              )}

              <Card style={styles.infoCard}>
                <Card.Content>
                  <Text style={styles.infoTitle}>Fees</Text>
                  <Text>
                    Fees and the final payout amount are calculated and confirmed by the
                    server before the transfer is sent.
                  </Text>
                </Card.Content>
              </Card>

              <Text style={styles.sectionHint}>Delivery Method</Text>
              <SegmentedButtons
                value={deliveryMethod}
                onValueChange={setDeliveryMethod}
                buttons={deliveryMethods.map((method) => ({ value: method.value, label: method.label }))}
                style={styles.input}
              />

              <TextInput
                label="Note (Optional)"
                value={note}
                onChangeText={setNote}
                mode="outlined"
                multiline
                numberOfLines={3}
                style={styles.input}
              />
            </>
          )}

          {step === 3 && (
            <>
              <Card style={styles.summaryCard}>
                <Card.Content>
                  <Text style={styles.summaryHead}>You send</Text>
                  <Text style={styles.summaryValue}>
                    {CURRENCY_SYMBOLS[currency] || ""}
                    {Number(amount || 0).toFixed(2)} {currency}
                  </Text>
                  <Text style={styles.summaryArrow}>↓</Text>
                  <Text style={styles.summaryHead}>Recipient gets (indicative, before fees)</Text>
                  <Text style={styles.summaryValue}>
                    {CURRENCY_SYMBOLS[destinationCurrency] || ""}
                    {receivedAmount} {destinationCurrency}
                  </Text>
                </Card.Content>
              </Card>

              <Card style={styles.infoCard}>
                <Card.Content>
                  <Text style={styles.infoTitle}>Recipient Details</Text>
                  <Text>Name: {recipientName}</Text>
                  <Text>{recipientType === "bank" ? "Account" : recipientType === "phone" ? "Phone" : "Email"}: {recipientAccount}</Text>
                  {!!bankCode && <Text>Bank Code: {bankCode}</Text>}
                </Card.Content>
              </Card>

              <Card style={styles.infoCard}>
                <Card.Content>
                  <Text style={styles.infoTitle}>Total Costs</Text>
                  <Text>Amount to send: {CURRENCY_SYMBOLS[currency] || ""}{Number(amount || 0).toFixed(2)}</Text>
                  <Text>
                    Applicable fees and the total to pay are confirmed by the server on
                    submission.
                  </Text>
                </Card.Content>
              </Card>
            </>
          )}

          <View style={styles.navRow}>
            {step > 1 ? (
              <Button mode="outlined" onPress={() => setStep((current) => current - 1)}>
                Back
              </Button>
            ) : (
              <View />
            )}
            <Button mode="contained" onPress={handleContinue} loading={submitting} disabled={submitting}>
              {step === 3 ? "Confirm Transfer" : "Continue"}
            </Button>
          </View>
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
  subtitle: { color: "#4B5563", marginTop: -6, marginBottom: 10 },
  stepperRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  stepItem: { flexDirection: "row", alignItems: "center", flex: 1 },
  stepCircle: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  stepCircleActive: { backgroundColor: "#2563EB" },
  stepCircleInactive: { backgroundColor: "#D1D5DB" },
  stepTextActive: { color: "#fff", fontWeight: "700" },
  stepTextInactive: { color: "#6B7280", fontWeight: "700" },
  stepLine: { flex: 1, height: 3, marginHorizontal: 6 },
  stepLineActive: { backgroundColor: "#2563EB" },
  stepLineInactive: { backgroundColor: "#E5E7EB" },
  stepLabels: { flexDirection: "row", justifyContent: "space-between", marginTop: 4, marginBottom: 6 },
  stepLabel: { color: "#6B7280", fontSize: 12 },
  card: { borderRadius: 12 },
  input: { marginBottom: 8 },
  row: { flexDirection: "row", gap: 8 },
  flex: { flex: 1 },
  currency: { width: 110 },
  sectionHint: { fontSize: 12, color: "#6B7280", marginBottom: 6 },
  currencyRow: { marginBottom: 8 },
  currencyBtn: { marginRight: 6 },
  infoCard: { borderRadius: 10, marginBottom: 8, backgroundColor: "#F9FAFB" },
  infoTitle: { fontWeight: "700", marginBottom: 4 },
  infoValue: { fontSize: 20, fontWeight: "700" },
  totalFees: { marginTop: 6, fontWeight: "700" },
  summaryCard: { borderRadius: 10, marginBottom: 8, backgroundColor: "#EFF6FF" },
  summaryHead: { textAlign: "center", color: "#1D4ED8", marginBottom: 2 },
  summaryValue: { textAlign: "center", fontSize: 22, fontWeight: "700", color: "#1E3A8A" },
  summaryArrow: { textAlign: "center", fontSize: 18, color: "#2563EB", marginVertical: 4 },
  navRow: { marginTop: 10, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  successRefLabel: { color: "#6B7280", marginBottom: 6 },
  successRef: { fontSize: 20, fontWeight: "700", marginBottom: 16 },
  successActions: { marginTop: 8 },
});
