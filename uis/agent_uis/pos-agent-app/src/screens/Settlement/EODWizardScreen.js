import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Button, Card, Divider, ProgressBar, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { commissionApi, ledgerApi } from "../../services/apiService";
import { spacing } from "../../theme";
const DENOMINATIONS = [
  { value: 1000, label: "₦1,000" },
  { value: 500, label: "₦500" },
  { value: 200, label: "₦200" },
  { value: 100, label: "₦100" },
  { value: 50, label: "₦50" },
  { value: 20, label: "₦20" },
  { value: 10, label: "₦10" },
  { value: 5, label: "₦5" },
];

const STEPS = ["Cash Count", "Review Txns", "Variance", "Submit"];
const TOLERANCE = 100; // ₦100 auto-flag threshold

export default function EODWizardScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [step, setStep] = useState(0);
  const [counts, setCounts] = useState(
    Object.fromEntries(DENOMINATIONS.map((d) => [d.value, 0])),
  );
  const [transactions, setTransactions] = useState([]);
  const [txnSummary, setTxnSummary] = useState(null);
  const [systemBalance, setSystemBalance] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [commissionEodResult, setCommissionEodResult] = useState(null);

  const physicalCash = Object.entries(counts).reduce(
    (sum, [denom, count]) => sum + Number(denom) * count,
    0,
  );

  const variance = physicalCash - systemBalance;
  const isBalanced = Math.abs(variance) <= TOLERANCE;

  const loadTodayTransactions = useCallback(async () => {
    try {
      setLoading(true);
      const accountNumber = await SecureStore.getItemAsync("accountNumber");
      if (!accountNumber) return;

      const res = await ledgerApi.getTransactionsByAccountNumber(accountNumber, 200, 1);
      const allTxns = res?.transactions || res?.data || [];
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const todayTxns = allTxns.filter((t) => new Date(t.created_at) >= today);
      setTransactions(todayTxns);

      const summary = todayTxns.reduce(
        (acc, t) => {
          const amount = parseFloat(t.amount || 0);
          const type = (t.transaction_type || "").toLowerCase();
          if (t.credit > 0 || type.includes("in") || type.includes("deposit")) {
            acc.cashIn += amount;
          } else if (type.includes("transfer")) {
            acc.transfers += amount;
          } else if (type.includes("bill")) {
            acc.bills += amount;
          } else {
            acc.cashOut += amount;
          }
          acc.total += 1;
          acc.netFlow += (t.credit > 0 ? 1 : -1) * amount;
          return acc;
        },
        { cashIn: 0, cashOut: 0, transfers: 0, bills: 0, total: 0, netFlow: 0 },
      );

      setTxnSummary(summary);
      setSystemBalance(Math.abs(summary.netFlow));
    } catch (err) {
      setError(err.message || "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (step === 1) {
      loadTodayTransactions();
    }
  }, [step, loadTodayTransactions]);

  const adjustCount = (denom, delta) => {
    setCounts((prev) => ({
      ...prev,
      [denom]: Math.max(0, (prev[denom] || 0) + delta),
    }));
  };

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      const agentId = await SecureStore.getItemAsync("agentId");
      const report = {
        agent_id: agentId,
        date: new Date().toISOString().split("T")[0],
        physical_cash: physicalCash,
        system_balance: systemBalance,
        variance,
        is_balanced: isBalanced,
        denomination_counts: counts,
        transaction_summary: txnSummary,
      };
      // Submit cash count EOD report (best-effort)
      await fetch("https://54agent.upi.dev/agent/agent/eod-reports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${await SecureStore.getItemAsync("authToken")}`,
        },
        body: JSON.stringify(report),
      }).catch(() => null);

      // Trigger commission settlement EOD (best-effort)
      const eodRes = await commissionApi.runEod().catch(() => null);
      if (eodRes) setCommissionEodResult(eodRes);

      setSubmitted(true);
    } catch (err) {
      setError(err.message || "Failed to submit EOD report");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <View style={styles.successContainer}>
        <Icon name="check-circle" size={72} color="#10B981" />
        <Text variant="headlineSmall" style={styles.successTitle}>
          EOD Report Submitted
        </Text>
        <Text variant="bodyMedium" style={styles.successSubtitle}>
          {isBalanced ? "Cash balanced successfully." : `Variance of ₦${Math.abs(variance).toLocaleString()} has been flagged for review.`}
        </Text>
        {commissionEodResult && (
          <Card style={{ width: "100%", marginTop: 16 }}>
            <Card.Content>
              <Text variant="titleSmall" style={{ fontWeight: "700", marginBottom: 8, color: "#111827" }}>
                Commission Settlements
              </Text>
              {[
                { label: "Agents processed", value: commissionEodResult.agents_processed ?? commissionEodResult.total ?? "—" },
                { label: "Successful", value: commissionEodResult.successful ?? "—" },
                { label: "Total paid", value: commissionEodResult.total_paid != null ? `₦${parseFloat(commissionEodResult.total_paid).toLocaleString()}` : "—" },
              ].map((item) => (
                <View key={item.label} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
                  <Text variant="bodySmall" style={{ color: "#6B7280" }}>{item.label}</Text>
                  <Text variant="bodySmall" style={{ fontWeight: "700" }}>{String(item.value)}</Text>
                </View>
              ))}
            </Card.Content>
          </Card>
        )}
        <Text variant="bodySmall" style={styles.successRef}>
          {new Date().toLocaleDateString("en-NG", { dateStyle: "full" })}
        </Text>
        <Button
          mode="contained"
          onPress={() => navigation.goBack()}
          style={styles.doneButton}
          buttoncolor={colors.primary}
        >
          Done
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Progress Header */}
      <View style={styles.progressContainer}>
        <View style={styles.stepsRow}>
          {STEPS.map((s, i) => (
            <View key={s} style={styles.stepItem}>
              <View
                style={[
                  styles.stepCircle,
                  i < step && styles.stepDone,
                  i === step && styles.stepActive,
                ]}
              >
                {i < step ? (
                  <Icon name="check" size={14} color="#fff" />
                ) : (
                  <Text style={[styles.stepNum, i === step && { color: "#fff" }]}>
                    {i + 1}
                  </Text>
                )}
              </View>
              <Text
                style={[styles.stepLabel, i === step && styles.stepLabelActive]}
              >
                {s}
              </Text>
            </View>
          ))}
        </View>
        <ProgressBar
          progress={(step + 1) / STEPS.length}
          color={colors.primary}
          style={styles.progressBar}
        />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Step 0: Physical Cash Count */}
        {step === 0 && (
          <View>
            <Text variant="titleMedium" style={styles.stepTitle}>
              Physical Cash Count
            </Text>
            <Text variant="bodySmall" style={styles.stepSubtitle}>
              Count each denomination and enter the quantity.
            </Text>

            {DENOMINATIONS.map((d) => (
              <Card key={d.value} style={styles.denomCard}>
                <Card.Content style={styles.denomRow}>
                  <Text variant="titleSmall" style={styles.denomLabel}>
                    {d.label}
                  </Text>
                  <View style={styles.denomControls}>
                    <TouchableOpacity
                      onPress={() => adjustCount(d.value, -1)}
                      style={[styles.denomBtn, styles.denomBtnMinus]}
                    >
                      <Icon name="minus" size={18} color="#EF4444" />
                    </TouchableOpacity>
                    <Text variant="titleMedium" style={styles.denomCount}>
                      {counts[d.value]}
                    </Text>
                    <TouchableOpacity
                      onPress={() => adjustCount(d.value, 1)}
                      style={[styles.denomBtn, styles.denomBtnPlus]}
                    >
                      <Icon name="plus" size={18} color="#10B981" />
                    </TouchableOpacity>
                  </View>
                  <Text variant="bodySmall" style={styles.denomSubtotal}>
                    ₦{(d.value * counts[d.value]).toLocaleString()}
                  </Text>
                </Card.Content>
              </Card>
            ))}

            <Card style={[styles.totalCard, { backgroundColor: colors.primary }]}>
              <Card.Content style={styles.totalRow}>
                <Text style={styles.totalLabel}>Total Physical Cash</Text>
                <Text style={styles.totalAmount}>
                  ₦{physicalCash.toLocaleString()}
                </Text>
              </Card.Content>
            </Card>
          </View>
        )}

        {/* Step 1: Review Transactions */}
        {step === 1 && (
          <View>
            <Text variant="titleMedium" style={styles.stepTitle}>
              Review Today's Transactions
            </Text>
            {loading ? (
              <Text style={styles.loadingText}>Loading transactions...</Text>
            ) : txnSummary ? (
              <View>
                {[
                  { label: "Cash In", value: txnSummary.cashIn, color: "#10B981", icon: "cash-plus" },
                  { label: "Cash Out", value: txnSummary.cashOut, color: "#EF4444", icon: "cash-minus" },
                  { label: "Transfers", value: txnSummary.transfers, color: colors.primary, icon: "bank-transfer" },
                  { label: "Bills", value: txnSummary.bills, color: "#F59E0B", icon: "receipt" },
                ].map((item) => (
                  <Card key={item.label} style={styles.txnCard}>
                    <Card.Content style={styles.txnRow}>
                      <View style={[styles.txnIcon, { backgroundColor: item.color + "20" }]}>
                        <Icon name={item.icon} size={20} color={item.color} />
                      </View>
                      <Text variant="bodyMedium" style={styles.txnLabel}>
                        {item.label}
                      </Text>
                      <Text
                        variant="titleSmall"
                        style={{ color: item.color, fontWeight: "700" }}
                      >
                        ₦{item.value.toLocaleString()}
                      </Text>
                    </Card.Content>
                  </Card>
                ))}
                <Card style={styles.txnCard}>
                  <Card.Content style={styles.txnRow}>
                    <View style={[styles.txnIcon, { backgroundColor: "#6B728020" }]}>
                      <Icon name="counter" size={20} color="#6B7280" />
                    </View>
                    <Text variant="bodyMedium" style={styles.txnLabel}>
                      Total Transactions
                    </Text>
                    <Text variant="titleSmall" style={{ fontWeight: "700" }}>
                      {txnSummary.total}
                    </Text>
                  </Card.Content>
                </Card>
              </View>
            ) : (
              <Text style={styles.loadingText}>No transactions today.</Text>
            )}
          </View>
        )}

        {/* Step 2: Variance Check */}
        {step === 2 && (
          <View>
            <Text variant="titleMedium" style={styles.stepTitle}>
              Variance Check
            </Text>
            <Card
              style={[
                styles.varianceCard,
                { borderColor: isBalanced ? "#10B981" : "#EF4444" },
              ]}
            >
              <Card.Content>
                <View style={styles.varianceRow}>
                  <Text variant="bodyMedium" style={styles.varianceLabel}>
                    Physical Cash
                  </Text>
                  <Text variant="titleSmall" style={{ fontWeight: "700" }}>
                    ₦{physicalCash.toLocaleString()}
                  </Text>
                </View>
                <Divider style={{ marginVertical: spacing.sm }} />
                <View style={styles.varianceRow}>
                  <Text variant="bodyMedium" style={styles.varianceLabel}>
                    System Balance
                  </Text>
                  <Text variant="titleSmall" style={{ fontWeight: "700" }}>
                    ₦{systemBalance.toLocaleString()}
                  </Text>
                </View>
                <Divider style={{ marginVertical: spacing.sm }} />
                <View style={styles.varianceRow}>
                  <Text variant="bodyMedium" style={[styles.varianceLabel, { fontWeight: "700" }]}>
                    Variance
                  </Text>
                  <Text
                    variant="titleMedium"
                    style={{
                      fontWeight: "700",
                      color: isBalanced ? "#10B981" : "#EF4444",
                    }}
                  >
                    {variance >= 0 ? "+" : ""}₦{variance.toLocaleString()}
                  </Text>
                </View>
              </Card.Content>
            </Card>

            <Card
              style={[
                styles.statusCard,
                {
                  backgroundColor: isBalanced ? "#ECFDF5" : "#FEF2F2",
                  borderColor: isBalanced ? "#10B981" : "#EF4444",
                },
              ]}
            >
              <Card.Content style={styles.statusRow}>
                <Icon
                  name={isBalanced ? "check-circle" : "alert-circle"}
                  size={28}
                  color={isBalanced ? "#10B981" : "#EF4444"}
                />
                <View style={{ marginLeft: spacing.sm, flex: 1 }}>
                  <Text
                    variant="titleSmall"
                    style={{
                      color: isBalanced ? "#065F46" : "#991B1B",
                      fontWeight: "700",
                    }}
                  >
                    {isBalanced ? "Balanced" : "Discrepancy Detected"}
                  </Text>
                  <Text
                    variant="bodySmall"
                    style={{ color: isBalanced ? "#065F46" : "#991B1B" }}
                  >
                    {isBalanced
                      ? `Within ₦${TOLERANCE} tolerance threshold.`
                      : `Variance exceeds ₦${TOLERANCE} threshold. Will be flagged for review.`}
                  </Text>
                </View>
              </Card.Content>
            </Card>
          </View>
        )}

        {/* Step 3: Submit */}
        {step === 3 && (
          <View>
            <Text variant="titleMedium" style={styles.stepTitle}>
              Submit EOD Report
            </Text>
            <Card style={styles.summaryCard}>
              <Card.Content>
                <Text variant="titleSmall" style={{ fontWeight: "700", marginBottom: spacing.md }}>
                  Summary
                </Text>
                {[
                  { label: "Date", value: new Date().toLocaleDateString("en-NG") },
                  { label: "Physical Cash", value: `₦${physicalCash.toLocaleString()}` },
                  { label: "System Balance", value: `₦${systemBalance.toLocaleString()}` },
                  {
                    label: "Variance",
                    value: `${variance >= 0 ? "+" : ""}₦${variance.toLocaleString()}`,
                    color: isBalanced ? "#10B981" : "#EF4444",
                  },
                  {
                    label: "Status",
                    value: isBalanced ? "Balanced" : "Discrepancy",
                    color: isBalanced ? "#10B981" : "#EF4444",
                  },
                  { label: "Total Transactions", value: txnSummary?.total || 0 },
                ].map((item, i) => (
                  <View key={item.label}>
                    <View style={styles.summaryRow}>
                      <Text variant="bodySmall" style={{ color: "#6B7280" }}>
                        {item.label}
                      </Text>
                      <Text
                        variant="bodyMedium"
                        style={{ fontWeight: "600", color: item.color || "#111827" }}
                      >
                        {item.value}
                      </Text>
                    </View>
                    {i < 5 && <Divider style={styles.divider} />}
                  </View>
                ))}
              </Card.Content>
            </Card>
          </View>
        )}
      </ScrollView>

      {/* Navigation Buttons */}
      <View style={styles.navContainer}>
        {step > 0 && (
          <Button
            mode="outlined"
            onPress={() => setStep((s) => s - 1)}
            style={styles.navBtn}
          >
            Back
          </Button>
        )}
        {step < STEPS.length - 1 ? (
          <Button
            mode="contained"
            onPress={() => setStep((s) => s + 1)}
            style={[styles.navBtn, { flex: 1 }]}
            buttoncolor={colors.primary}
          >
            Next
          </Button>
        ) : (
          <Button
            mode="contained"
            onPress={handleSubmit}
            loading={submitting}
            style={[styles.navBtn, { flex: 1 }]}
            buttonColor="#10B981"
            icon="check"
          >
            Submit EOD Report
          </Button>
        )}
      </View>

      <Snackbar visible={!!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  progressContainer: {
    backgroundColor: "#fff",
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  stepsRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  stepItem: { alignItems: "center", flex: 1 },
  stepCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#E5E7EB",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 4,
  },
  stepActive: { backgroundColor: colors.primary },
  stepDone: { backgroundColor: "#10B981" },
  stepNum: { fontSize: 13, fontWeight: "700", color: "#9CA3AF" },
  stepLabel: { fontSize: 10, color: "#9CA3AF", textAlign: "center" },
  stepLabelActive: { color: colors.primary, fontWeight: "600" },
  progressBar: { height: 3, borderRadius: 2 },
  content: { flex: 1, padding: spacing.md },
  stepTitle: { fontWeight: "700", color: "#111827", marginBottom: spacing.xs },
  stepSubtitle: { color: "#6B7280", marginBottom: spacing.md },
  loadingText: { color: "#6B7280", textAlign: "center", marginTop: spacing.xl },
  denomCard: { marginBottom: spacing.sm },
  denomRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  denomLabel: { fontWeight: "600", width: 60 },
  denomControls: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  denomBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  denomBtnMinus: { backgroundColor: "#FEF2F2" },
  denomBtnPlus: { backgroundColor: "#ECFDF5" },
  denomCount: { fontWeight: "700", minWidth: 30, textAlign: "center" },
  denomSubtotal: { color: "#6B7280", minWidth: 70, textAlign: "right" },
  totalCard: { marginTop: spacing.md, marginBottom: spacing.xl },
  totalRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  totalLabel: { color: "#fff", fontSize: 16, fontWeight: "600" },
  totalAmount: { color: "#fff", fontSize: 22, fontWeight: "700" },
  txnCard: { marginBottom: spacing.sm },
  txnRow: { flexDirection: "row", alignItems: "center" },
  txnIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.sm,
  },
  txnLabel: { flex: 1, color: "#374151" },
  varianceCard: { borderWidth: 2, borderRadius: 8, marginBottom: spacing.md },
  varianceRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  varianceLabel: { color: "#374151" },
  statusCard: { borderWidth: 2, borderRadius: 8 },
  statusRow: { flexDirection: "row", alignItems: "center" },
  summaryCard: { marginBottom: spacing.lg },
  summaryRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.sm },
  divider: { backgroundColor: "#F3F4F6" },
  navContainer: {
    flexDirection: "row",
    padding: spacing.md,
    gap: spacing.md,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
  },
  navBtn: { borderRadius: 8 },
  successContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: "#F9FAFB",
  },
  successTitle: { fontWeight: "700", marginTop: spacing.lg, color: "#111827", textAlign: "center" },
  successSubtitle: { color: "#6B7280", marginTop: spacing.sm, textAlign: "center" },
  successRef: { color: "#9CA3AF", marginTop: spacing.sm },
  doneButton: { marginTop: spacing.xl, width: "100%", borderRadius: 8 },
});
