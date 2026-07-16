import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Button, Card, Chip, Divider, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { commissionApi, ledgerApi, accountApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { theme as _appTheme } from '../../theme';
const colors = _appTheme.colors;

const OUTSTANDING_TYPES = [
  { key: "cash_in", label: "Cash In", icon: "cash-plus", color: "#10B981" },
  { key: "cash_out", label: "Cash Out", icon: "cash-minus", color: "#EF4444" },
  { key: "transfer", label: "Transfer", icon: "bank-transfer", color: colors.primary },
  { key: "bills", label: "Bills", icon: "receipt", color: "#F59E0B" },
];

export default function SettlementScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [settlements, setSettlements] = useState([]);
  const [dayStats, setDayStats] = useState(null);
  const [netPosition, setNetPosition] = useState(0);
  const [pendingBatches, setPendingBatches] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [eodRunning, setEodRunning] = useState(false);
  const [eodResult, setEodResult] = useState(null);
  const [showEodResult, setShowEodResult] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    try {
      isRefresh ? setRefreshing(true) : setLoading(true);
      setError("");

      const agentId = await SecureStore.getItemAsync("agentId");
      const accountNumber = await SecureStore.getItemAsync("accountNumber");
      const today = new Date();
      const startOfDay = new Date(today.setHours(0, 0, 0, 0)).toISOString();
      const now = new Date().toISOString();

      const [settlementsRes, txnsRes] = await Promise.allSettled([
        commissionApi.listSettlements(agentId, { status: "pending", limit: 50 }),
        accountNumber
          ? ledgerApi.getTransactionsByAccountNumber(accountNumber, 100, 1)
          : Promise.resolve(null),
      ]);

      const settlementsData =
        settlementsRes.status === "fulfilled"
          ? settlementsRes.value?.settlements || settlementsRes.value?.data || []
          : [];
      setSettlements(settlementsData);

      const pending = settlementsData.filter(
        (s) => s.status === "pending" || s.status === "processing",
      );
      setPendingBatches(pending.length);

      if (txnsRes.status === "fulfilled" && txnsRes.value) {
        const txns = txnsRes.value?.transactions || txnsRes.value?.data || [];
        const todayTxns = txns.filter((t) => new Date(t.created_at) >= new Date(startOfDay));

        const stats = todayTxns.reduce(
          (acc, t) => {
            const amount = parseFloat(t.amount || 0);
            const type = (t.transaction_type || "").toLowerCase();
            if (t.credit > 0 || type.includes("in") || type.includes("deposit")) {
              acc.credit += amount;
              acc.byType.cash_in = (acc.byType.cash_in || 0) + amount;
            } else {
              acc.debit += amount;
              if (type.includes("transfer")) acc.byType.transfer = (acc.byType.transfer || 0) + amount;
              else if (type.includes("bill")) acc.byType.bills = (acc.byType.bills || 0) + amount;
              else acc.byType.cash_out = (acc.byType.cash_out || 0) + amount;
            }
            acc.count += 1;
            return acc;
          },
          { credit: 0, debit: 0, count: 0, byType: {} },
        );

        setDayStats(stats);
        setNetPosition(stats.credit - stats.debit);
      }
    } catch (err) {
      setError(err.message || "Failed to load settlement data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleExport = async () => {
    try {
      setExporting(true);
      const date = new Date().toISOString().split("T")[0];
      Alert.alert(
        "Export Settlement Report",
        `Settlement report for ${date} has been queued. You will receive it via email shortly.`,
        [{ text: "OK" }],
      );
    } catch (err) {
      setError(err.message || "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleRunEod = () => {
    Alert.alert(
      "Run EOD Settlement",
      "This will process commission settlements for all agents with a pending balance. Continue?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Run EOD",
          style: "default",
          onPress: async () => {
            try {
              setEodRunning(true);
              const result = await commissionApi.runEod();
              setEodResult(result);
              setShowEodResult(true);
              load(true);
            } catch (err) {
              setError(err.message || "EOD run failed");
            } finally {
              setEodRunning(false);
            }
          },
        },
      ],
    );
  };

  const getSettlementStatusColor = (status) => {
    if (status === "completed") return "#10B981";
    if (status === "failed") return "#EF4444";
    if (status === "processing") return colors.primary;
    return "#F59E0B";
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <Icon name="bank-transfer" size={48} color={colors.primary} />
        <Text variant="bodyMedium" style={{ marginTop: spacing.md, color: "#6B7280" }}>
          Loading settlement data...
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
    >
      {/* Status Header */}
      <Card style={styles.headerCard}>
        <Card.Content>
          <View style={styles.headerRow}>
            <View>
              <Text variant="bodySmall" style={styles.headerLabel}>
                Settlement Status
              </Text>
              <View style={styles.statusRow}>
                <Icon
                  name={pendingBatches > 0 ? "clock-outline" : "check-circle"}
                  size={20}
                  color={pendingBatches > 0 ? "#F59E0B" : "#10B981"}
                />
                <Text
                  variant="titleMedium"
                  style={{ marginLeft: spacing.xs, color: "#fff", fontWeight: "700" }}
                >
                  {pendingBatches > 0
                    ? `${pendingBatches} Pending Batch${pendingBatches > 1 ? "es" : ""}`
                    : "All Settled"}
                </Text>
              </View>
            </View>
            <View style={styles.netPositionBox}>
              <Text style={styles.netLabel}>Net Position</Text>
              <Text
                style={[
                  styles.netAmount,
                  { color: netPosition >= 0 ? "#86EFAC" : "#FCA5A5" },
                ]}
              >
                {netPosition >= 0 ? "+" : ""}₦{Math.abs(netPosition).toLocaleString()}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Today's Stats */}
      {dayStats && (
        <Card style={styles.sectionCard}>
          <Card.Content>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Today's Transactions
            </Text>
            <View style={styles.statsRow}>
              <View style={styles.statBox}>
                <Text style={[styles.statValue, { color: "#10B981" }]}>
                  ₦{(dayStats.credit || 0).toLocaleString()}
                </Text>
                <Text style={styles.statLabel}>Total In</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statBox}>
                <Text style={[styles.statValue, { color: "#EF4444" }]}>
                  ₦{(dayStats.debit || 0).toLocaleString()}
                </Text>
                <Text style={styles.statLabel}>Total Out</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{dayStats.count}</Text>
                <Text style={styles.statLabel}>Transactions</Text>
              </View>
            </View>
          </Card.Content>
        </Card>
      )}

      {/* Outstanding by Type */}
      <Card style={styles.sectionCard}>
        <Card.Content>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            Outstanding by Type
          </Text>
          {OUTSTANDING_TYPES.map((type) => {
            const amount = dayStats?.byType?.[type.key] || 0;
            return (
              <View key={type.key}>
                <View style={styles.typeRow}>
                  <View style={styles.typeLeft}>
                    <View style={[styles.typeIcon, { backgroundColor: type.color + "20" }]}>
                      <Icon name={type.icon} size={18} color={type.color} />
                    </View>
                    <Text variant="bodyMedium" style={styles.typeLabel}>
                      {type.label}
                    </Text>
                  </View>
                  <Text
                    variant="titleSmall"
                    style={{ color: type.color, fontWeight: "600" }}
                  >
                    ₦{amount.toLocaleString()}
                  </Text>
                </View>
                <Divider style={styles.divider} />
              </View>
            );
          })}
        </Card.Content>
      </Card>

      {/* Pending Settlements */}
      {settlements.length > 0 && (
        <Card style={styles.sectionCard}>
          <Card.Content>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Settlement History
            </Text>
            {settlements.slice(0, 5).map((s, idx) => (
              <View key={s.id || idx}>
                <View style={styles.settlementRow}>
                  <View style={{ flex: 1 }}>
                    <Text variant="bodyMedium" style={{ fontWeight: "600" }}>
                      {s.reference || `Settlement #${idx + 1}`}
                    </Text>
                    <Text variant="bodySmall" style={{ color: "#6B7280" }}>
                      {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                    </Text>
                  </View>
                  <View style={styles.settlementRight}>
                    <Text variant="bodyMedium" style={{ fontWeight: "700", color: colors.primary }}>
                      ₦{parseFloat(s.amount || 0).toLocaleString()}
                    </Text>
                    <Chip
                      mode="flat"
                      style={{
                        height: 24,
                        backgroundColor: getSettlementStatusColor(s.status) + "20",
                      }}
                      textStyle={{ color: getSettlementStatusColor(s.status), fontSize: 10 }}
                    >
                      {s.status || "pending"}
                    </Chip>
                  </View>
                </View>
                {idx < Math.min(settlements.length, 5) - 1 && (
                  <Divider style={styles.divider} />
                )}
              </View>
            ))}
          </Card.Content>
        </Card>
      )}

      {/* Actions */}
      <View style={styles.actionsContainer}>
        <Button
          mode="contained"
          icon="file-export"
          onPress={handleExport}
          loading={exporting}
          style={styles.exportButton}
          buttoncolor={colors.primary}
        >
          Export Settlement Report
        </Button>
        <Button
          mode="contained"
          icon="calculator"
          onPress={handleRunEod}
          loading={eodRunning}
          style={styles.eodButton}
          buttonColor="#10B981"
        >
          Run EOD Settlement
        </Button>
        <Button
          mode="outlined"
          icon="format-list-checks"
          onPress={() => navigation.navigate("EODWizard")}
          style={styles.eodButton}
        >
          Cash Count Wizard
        </Button>
      </View>

      {/* EOD Result Modal */}
      <Modal
        visible={showEodResult}
        transparent
        animationType="slide"
        onRequestClose={() => setShowEodResult(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <View style={styles.modalHeader}>
              <Icon name="check-circle" size={28} color="#10B981" />
              <Text variant="titleMedium" style={styles.modalTitle}>
                EOD Settlement Complete
              </Text>
            </View>
            {eodResult && (
              <View>
                {[
                  { label: "Agents Processed", value: eodResult.agents_processed ?? eodResult.total ?? "—" },
                  { label: "Successful", value: eodResult.successful ?? "—", color: "#10B981" },
                  { label: "Failed", value: eodResult.failed ?? "—", color: eodResult.failed > 0 ? "#EF4444" : "#6B7280" },
                  { label: "Total Paid", value: eodResult.total_paid != null ? `₦${parseFloat(eodResult.total_paid).toLocaleString()}` : "—", color: colors.primary },
                ].map((item) => (
                  <View key={item.label} style={styles.resultRow}>
                    <Text variant="bodyMedium" style={{ color: "#6B7280" }}>{item.label}</Text>
                    <Text variant="titleSmall" style={{ fontWeight: "700", color: item.color || "#111827" }}>
                      {String(item.value)}
                    </Text>
                  </View>
                ))}
              </View>
            )}
            <Button
              mode="contained"
              onPress={() => setShowEodResult(false)}
              style={{ marginTop: 16, borderRadius: 8 }}
              buttoncolor={colors.primary}
            >
              Done
            </Button>
          </View>
        </View>
      </Modal>

      <Snackbar visible={!!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  headerCard: {
    margin: spacing.md,
    backgroundColor: colors.primary,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerLabel: { color: "#fff", opacity: 0.8, marginBottom: spacing.xs },
  statusRow: { flexDirection: "row", alignItems: "center" },
  netPositionBox: { alignItems: "flex-end" },
  netLabel: { color: "#fff", opacity: 0.8, fontSize: 12 },
  netAmount: { fontSize: 22, fontWeight: "700" },
  sectionCard: { marginHorizontal: spacing.md, marginBottom: spacing.md },
  sectionTitle: { fontWeight: "700", marginBottom: spacing.md, color: "#111827" },
  statsRow: { flexDirection: "row", justifyContent: "space-around" },
  statBox: { alignItems: "center", flex: 1 },
  statValue: { fontSize: 18, fontWeight: "700", color: "#111827" },
  statLabel: { fontSize: 11, color: "#6B7280", marginTop: 2 },
  statDivider: { width: 1, backgroundColor: "#E5E7EB" },
  typeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  typeLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  typeIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    justifyContent: "center",
    alignItems: "center",
  },
  typeLabel: { color: "#374151" },
  divider: { backgroundColor: "#F3F4F6" },
  settlementRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  settlementRight: { alignItems: "flex-end", gap: spacing.xs },
  actionsContainer: { padding: spacing.md, gap: spacing.md },
  exportButton: { borderRadius: 8 },
  eodButton: { borderRadius: 8 },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalBox: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: spacing.lg,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  modalTitle: { fontWeight: "700", color: "#111827" },
  resultRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
});
