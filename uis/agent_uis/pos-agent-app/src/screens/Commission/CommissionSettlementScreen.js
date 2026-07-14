import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Button, Chip, Divider, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { commissionApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { theme as _appTheme } from '../../theme';
const colors = _appTheme.colors;

const fmt = (n) => `₦${parseFloat(n || 0).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS_COLOR = {
  pending:    "#F59E0B",
  settled:    "#10B981",
  completed:  "#10B981",
  cancelled:  "#6B7280",
  disputed:   "#EF4444",
  failed:     "#EF4444",
  processing: colors.primary,
};

const TX_LABEL = {
  deposit:      "Cash In",
  withdrawal:   "Cash Out",
  transfer:     "Transfer",
  bill_payment: "Bill Payment",
  airtime:      "Airtime",
  data:         "Data",
};

export default function CommissionSettlementScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [agentId, setAgentId]             = useState(null);
  const [balance, setBalance]             = useState(null);
  const [commissions, setCommissions]     = useState([]);
  const [settlements, setSettlements]     = useState([]);
  const [settlementFilter, setSettlementFilter] = useState("all");
  const [activeTab, setActiveTab]         = useState("commissions");
  const [searchQuery, setSearchQuery]     = useState("");
  const [loading, setLoading]             = useState(true);
  const [refreshing, setRefreshing]       = useState(false);
  const [error, setError]                 = useState("");
  const [success, setSuccess]             = useState("");

  // Policy
  const [withdrawalAllowed, setWithdrawalAllowed]       = useState(true);
  const [minWithdrawalAmount, setMinWithdrawalAmount]   = useState(0);

  // Withdraw modal
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [withdrawing, setWithdrawing]             = useState(false);
  const [bankName, setBankName]                   = useState("");
  const [accountNumber, setAccountNumber]         = useState("");
  const [accountName, setAccountName]             = useState("");

  const load = useCallback(async (isRefresh = false) => {
    try {
      isRefresh ? setRefreshing(true) : setLoading(true);
      setError("");

      const id = await SecureStore.getItemAsync("agentId");
      setAgentId(id);

      const now = new Date();
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
      const today        = now.toISOString().slice(0, 10);

      const [balRes, commRes, settRes, policyRes] = await Promise.allSettled([
        commissionApi.getBalance(id),
        commissionApi.listCommissions(id, { start_date: startOfMonth, end_date: today, limit: 100 }),
        commissionApi.listSettlements(id, { limit: 30 }),
        commissionApi.getPolicy(),
      ]);

      if (balRes.status === "fulfilled") setBalance(balRes.value);
      if (commRes.status === "fulfilled")
        setCommissions(commRes.value?.commissions ?? commRes.value?.data ?? []);
      if (settRes.status === "fulfilled")
        setSettlements(settRes.value?.settlements ?? settRes.value?.data ?? []);
      if (policyRes.status === "fulfilled") {
        setWithdrawalAllowed(policyRes.value?.allow_agent_withdrawal !== false);
        setMinWithdrawalAmount(parseFloat(policyRes.value?.min_withdrawal_amount ?? 0));
      }
    } catch (err) {
      setError(err.message || "Failed to load commission data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Derived balances
  const pendingBalance    = parseFloat(balance?.pending_balance   ?? 0);
  const availableBalance  = parseFloat(balance?.available_balance ?? 0);
  const settledBalance    = parseFloat(balance?.settled_balance   ?? 0);
  const totalEarned       = parseFloat(balance?.total_earned      ?? 0);
  const withdrawableAmount = availableBalance > 0 ? availableBalance : pendingBalance;
  const canWithdraw = withdrawalAllowed
    && withdrawableAmount >= minWithdrawalAmount
    && withdrawableAmount > 0;

  const handleWithdraw = async () => {
    if (!withdrawalAllowed) {
      Alert.alert("Withdrawals Paused", "Withdrawals are currently paused by the platform administrator.");
      return;
    }
    if (withdrawableAmount < minWithdrawalAmount) {
      Alert.alert("Minimum Not Met", `Minimum withdrawal amount is ${fmt(minWithdrawalAmount)}.`);
      return;
    }
    if (!bankName.trim() || !accountNumber.trim() || !accountName.trim()) {
      setError("Please fill in all bank details.");
      return;
    }

    setWithdrawing(true);
    setError("");
    try {
      const now   = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
      const end   = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59).toISOString();

      const settlement = await commissionApi.requestSettlement({
        agent_id:       agentId,
        payment_method: "bank_transfer",
        payment_details: {
          bank_name:      bankName.trim(),
          account_number: accountNumber.trim(),
          account_name:   accountName.trim(),
        },
        start_date:   start,
        end_date:     end,
        auto_process: true,
      });

      setShowWithdrawModal(false);
      setBankName(""); setAccountNumber(""); setAccountName("");

      const msg = settlement?.status === "completed"
        ? "Withdrawal processed — funds en route to your account."
        : "Withdrawal request submitted — pending processing.";
      setSuccess(msg);
      await load(true);
    } catch (err) {
      setError(err.message || "Withdrawal failed. Please try again.");
    } finally {
      setWithdrawing(false);
    }
  };

  const filteredCommissions = commissions.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.transaction_type?.toLowerCase().includes(q) ||
      c.transaction_ref?.toLowerCase().includes(q)
    );
  });

  const visibleSettlements = settlementFilter === "all"
    ? settlements
    : settlements.filter((s) => s.status === settlementFilter);

  const renderCommission = ({ item: c }) => (
    <View style={styles.listRow}>
      <View style={[styles.txIcon, { backgroundColor: "#10B98120" }]}>
        <Icon name="percent" size={16} color="#10B981" />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle}>{TX_LABEL[c.transaction_type] ?? c.transaction_type ?? "Commission"}</Text>
        <Text style={styles.rowSub} numberOfLines={1}>Ref: {c.transaction_ref ?? "—"}</Text>
        <Text style={styles.rowDate}>{c.earned_at ? new Date(c.earned_at).toLocaleDateString("en-NG") : "—"}</Text>
      </View>
      <View style={{ alignItems: "flex-end", gap: 4 }}>
        <Text style={styles.rowAmount}>{fmt(c.commission_amount)}</Text>
        <Text style={styles.rowRate}>{((c.rate ?? 0) * 100).toFixed(2)}%</Text>
        <Chip
          mode="flat"
          style={[styles.chip, { backgroundColor: (STATUS_COLOR[c.status] ?? "#6B7280") + "20" }]}
          textStyle={{ color: STATUS_COLOR[c.status] ?? "#6B7280", fontSize: 10 }}
        >
          {c.status ?? "pending"}
        </Chip>
      </View>
    </View>
  );

  const renderSettlement = ({ item: s }) => (
    <View style={styles.listRow}>
      <View style={[styles.txIcon, { backgroundColor: (STATUS_COLOR[s.status] ?? "#F59E0B") + "20" }]}>
        <Icon name={s.status === "completed" ? "check-circle" : s.status === "failed" ? "close-circle" : "clock-outline"}
          size={16} color={STATUS_COLOR[s.status] ?? "#F59E0B"} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle}>{s.settlement_ref ?? `Settlement`}</Text>
        <Text style={styles.rowSub}>{s.payment_method?.replace(/_/g, " ") ?? "bank transfer"} · {s.commission_count ?? 0} commissions</Text>
        <Text style={styles.rowDate}>{s.created_at ? new Date(s.created_at).toLocaleDateString("en-NG") : "—"}</Text>
      </View>
      <View style={{ alignItems: "flex-end", gap: 4 }}>
        <Text style={styles.rowAmount}>{fmt(s.total_amount)}</Text>
        <Chip
          mode="flat"
          style={[styles.chip, { backgroundColor: (STATUS_COLOR[s.status] ?? "#F59E0B") + "20" }]}
          textStyle={{ color: STATUS_COLOR[s.status] ?? "#F59E0B", fontSize: 10 }}
        >
          {s.status ?? "pending"}
        </Chip>
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#10B981" />
        <Text style={{ color: "#6B7280", marginTop: spacing.md }}>Loading commission data…</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: "#F9FAFB" }}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      >
        {/* Hero balance card */}
        <View style={styles.heroCard}>
          <View style={styles.heroRow}>
            <View style={styles.heroIconWrap}>
              <Icon name="wallet" size={28} color="#fff" />
            </View>
            <Text style={styles.heroLabel}>Commission Wallet</Text>
          </View>

          <Text style={styles.heroAmount}>{fmt(pendingBalance + availableBalance)}</Text>

          {!withdrawalAllowed && (
            <View style={styles.policyBanner}>
              <Icon name="lock" size={13} color="#fff" />
              <Text style={styles.policyBannerText}>Withdrawals paused by administrator</Text>
            </View>
          )}
          {withdrawalAllowed && minWithdrawalAmount > 0 && (
            <Text style={styles.heroSub}>Min. withdrawal: {fmt(minWithdrawalAmount)}</Text>
          )}

          {/* Balance breakdown */}
          <View style={styles.balanceGrid}>
            {[
              { label: "Pending",   value: pendingBalance,   color: "#FCD34D" },
              { label: "Available", value: availableBalance,  color: "#86EFAC" },
              { label: "Settled",   value: settledBalance,   color: "#fff" },
              { label: "Lifetime",  value: totalEarned,      color: "#fff" },
            ].map((b) => (
              <View key={b.label} style={styles.balanceCell}>
                <Text style={[styles.balanceCellAmount, { color: b.color }]}>{fmt(b.value)}</Text>
                <Text style={styles.balanceCellLabel}>{b.label}</Text>
              </View>
            ))}
          </View>

          <Button
            mode="contained"
            onPress={() => setShowWithdrawModal(true)}
            disabled={!canWithdraw}
            loading={false}
            icon="bank-transfer"
            buttonColor="#fff"
            textColor="#10B981"
            style={styles.withdrawBtn}
          >
            {canWithdraw ? "Withdraw Earnings" : !withdrawalAllowed ? "Withdrawals Paused" : "Nothing to Withdraw"}
          </Button>
        </View>

        {/* Tabs */}
        <View style={styles.tabRow}>
          {[
            { key: "commissions", label: "Commissions" },
            { key: "withdrawals", label: "Withdrawals" },
          ].map((t) => (
            <TouchableOpacity
              key={t.key}
              onPress={() => setActiveTab(t.key)}
              style={[styles.tab, activeTab === t.key && styles.tabActive]}
            >
              <Text style={[styles.tabText, activeTab === t.key && styles.tabTextActive]}>
                {t.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {activeTab === "commissions" && (
          <View style={styles.listSection}>
            {/* Search */}
            <View style={styles.searchWrap}>
              <Icon name="magnify" size={18} color="#9CA3AF" style={styles.searchIcon} />
              <TextInput
                style={styles.searchInput}
                placeholder="Search by type or ref..."
                placeholderTextColor="#9CA3AF"
                value={searchQuery}
                onChangeText={setSearchQuery}
              />
            </View>

            {filteredCommissions.length === 0 ? (
              <View style={styles.emptyWrap}>
                <Icon name="cash-multiple" size={48} color="#D1D5DB" />
                <Text style={styles.emptyText}>No commissions this month</Text>
                <Text style={styles.emptySub}>Complete transactions to start earning</Text>
              </View>
            ) : (
              <FlatList
                data={filteredCommissions}
                renderItem={renderCommission}
                keyExtractor={(c, i) => c.id ?? i.toString()}
                ItemSeparatorComponent={() => <Divider style={{ backgroundColor: "#F3F4F6" }} />}
                scrollEnabled={false}
              />
            )}
          </View>
        )}

        {activeTab === "withdrawals" && (
          <View style={styles.listSection}>
            {/* Filter chips */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.md }}>
              <View style={{ flexDirection: "row", gap: spacing.sm }}>
                {["all", "pending", "processing", "completed", "failed"].map((f) => (
                  <Chip
                    key={f}
                    mode={settlementFilter === f ? "flat" : "outlined"}
                    onPress={() => setSettlementFilter(f)}
                    style={settlementFilter === f ? styles.filterChipActive : styles.filterChip}
                    textStyle={{ fontSize: 12 }}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </Chip>
                ))}
              </View>
            </ScrollView>

            {visibleSettlements.length === 0 ? (
              <View style={styles.emptyWrap}>
                <Icon name="clock-outline" size={48} color="#D1D5DB" />
                <Text style={styles.emptyText}>No withdrawals yet</Text>
                <Text style={styles.emptySub}>Your withdrawal history will appear here</Text>
              </View>
            ) : (
              <FlatList
                data={visibleSettlements}
                renderItem={renderSettlement}
                keyExtractor={(s, i) => s.id ?? i.toString()}
                ItemSeparatorComponent={() => <Divider style={{ backgroundColor: "#F3F4F6" }} />}
                scrollEnabled={false}
              />
            )}
          </View>
        )}

        <View style={{ height: spacing.xl }} />
      </ScrollView>

      {/* Withdraw modal */}
      <Modal visible={showWithdrawModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Withdraw Earnings</Text>
              <TouchableOpacity onPress={() => setShowWithdrawModal(false)}>
                <Icon name="close" size={22} color="#6B7280" />
              </TouchableOpacity>
            </View>

            {/* Amount summary */}
            <View style={styles.modalBalancePill}>
              <Icon name="wallet" size={16} color="#10B981" />
              <Text style={styles.modalBalanceLabel}>Available to withdraw</Text>
              <Text style={styles.modalBalanceAmount}>{fmt(withdrawableAmount)}</Text>
            </View>

            {/* Bank details */}
            {[
              { label: "Beneficiary Bank", value: bankName,       setter: setBankName,       placeholder: "e.g. Access Bank" },
              { label: "Account Number",   value: accountNumber,  setter: setAccountNumber,  placeholder: "10-digit NUBAN",  keyboardType: "numeric" },
              { label: "Account Name",     value: accountName,    setter: setAccountName,    placeholder: "Name on account" },
            ].map((f) => (
              <View key={f.label} style={styles.fieldWrap}>
                <Text style={styles.fieldLabel}>{f.label}</Text>
                <TextInput
                  style={styles.fieldInput}
                  value={f.value}
                  onChangeText={f.setter}
                  placeholder={f.placeholder}
                  placeholderTextColor="#9CA3AF"
                  keyboardType={f.keyboardType}
                />
              </View>
            ))}

            <Text style={styles.modalNote}>
              Funds are transferred from the platform commission pool to your bank account. Typically processed within 24 hours.
            </Text>

            {!!error && (
              <View style={styles.modalError}>
                <Icon name="alert-circle" size={14} color="#EF4444" />
                <Text style={styles.modalErrorText}>{error}</Text>
              </View>
            )}

            <View style={styles.modalButtons}>
              <Button
                mode="outlined"
                onPress={() => { setShowWithdrawModal(false); setError(""); }}
                style={{ flex: 1 }}
              >
                Cancel
              </Button>
              <Button
                mode="contained"
                onPress={handleWithdraw}
                disabled={withdrawing || !bankName || !accountNumber || !accountName}
                loading={withdrawing}
                buttonColor="#10B981"
                style={{ flex: 1 }}
              >
                {withdrawing ? "Processing…" : "Confirm"}
              </Button>
            </View>
          </View>
        </View>
      </Modal>

      <Snackbar visible={!!success} onDismiss={() => setSuccess("")} duration={4000} style={styles.successSnack}>
        {success}
      </Snackbar>
      <Snackbar visible={!showWithdrawModal && !!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },

  // Hero
  heroCard: {
    margin: spacing.md,
    borderRadius: 16,
    backgroundColor: "#10B981",
    padding: spacing.lg,
  },
  heroRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  heroIconWrap: { width: 40, height: 40, borderRadius: 20, backgroundColor: "rgba(255,255,255,0.2)", justifyContent: "center", alignItems: "center" },
  heroLabel: { color: "rgba(255,255,255,0.85)", fontSize: 13, fontWeight: "600" },
  heroAmount: { color: "#fff", fontSize: 36, fontWeight: "800", marginVertical: spacing.xs },
  heroSub: { color: "rgba(255,255,255,0.75)", fontSize: 12, marginBottom: spacing.sm },
  policyBanner: { flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: "rgba(0,0,0,0.15)", borderRadius: 6, paddingHorizontal: spacing.sm, paddingVertical: 4, marginBottom: spacing.sm, alignSelf: "flex-start" },
  policyBannerText: { color: "#fff", fontSize: 11 },
  balanceGrid: { flexDirection: "row", flexWrap: "wrap", marginTop: spacing.md, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.2)", paddingTop: spacing.md, gap: 0 },
  balanceCell: { width: "50%", paddingBottom: spacing.sm },
  balanceCellAmount: { fontSize: 15, fontWeight: "700" },
  balanceCellLabel: { color: "rgba(255,255,255,0.7)", fontSize: 11, marginTop: 1 },
  withdrawBtn: { marginTop: spacing.md, borderRadius: 8 },

  // Tabs
  tabRow: { flexDirection: "row", backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#E5E7EB" },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabActive: { borderBottomColor: "#10B981" },
  tabText: { fontSize: 13, color: "#6B7280", fontWeight: "500" },
  tabTextActive: { color: "#10B981", fontWeight: "700" },

  // List
  listSection: { backgroundColor: "#fff", padding: spacing.md },
  searchWrap: { flexDirection: "row", alignItems: "center", backgroundColor: "#F3F4F6", borderRadius: 8, paddingHorizontal: spacing.sm, marginBottom: spacing.md },
  searchIcon: { marginRight: spacing.xs },
  searchInput: { flex: 1, height: 40, fontSize: 14, color: "#111827" },
  listRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.md },
  txIcon: { width: 36, height: 36, borderRadius: 18, justifyContent: "center", alignItems: "center" },
  rowTitle: { fontSize: 13, fontWeight: "600", color: "#111827", textTransform: "capitalize" },
  rowSub: { fontSize: 11, color: "#6B7280", marginTop: 1 },
  rowDate: { fontSize: 11, color: "#9CA3AF", marginTop: 1 },
  rowAmount: { fontSize: 13, fontWeight: "700", color: "#10B981" },
  rowRate: { fontSize: 11, color: "#6B7280" },
  chip: { height: 20, minWidth: 56 },
  filterChip: { borderColor: "#E5E7EB" },
  filterChipActive: { backgroundColor: "#10B981" },
  emptyWrap: { padding: spacing.xl, alignItems: "center" },
  emptyText: { marginTop: spacing.md, fontWeight: "600", color: "#374151" },
  emptySub: { color: "#9CA3AF", marginTop: spacing.xs, textAlign: "center" },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: spacing.lg, paddingBottom: spacing.xl },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg },
  modalTitle: { fontSize: 17, fontWeight: "700", color: "#111827" },
  modalBalancePill: { flexDirection: "row", alignItems: "center", backgroundColor: "#F0FDF4", borderRadius: 10, padding: spacing.md, gap: spacing.sm, marginBottom: spacing.lg },
  modalBalanceLabel: { flex: 1, fontSize: 13, color: "#065F46", fontWeight: "500" },
  modalBalanceAmount: { fontSize: 17, fontWeight: "800", color: "#10B981" },
  fieldWrap: { marginBottom: spacing.md },
  fieldLabel: { fontSize: 12, fontWeight: "600", color: "#374151", marginBottom: 4 },
  fieldInput: { borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 8, paddingHorizontal: spacing.md, height: 44, fontSize: 14, color: "#111827" },
  modalNote: { fontSize: 11, color: "#6B7280", backgroundColor: "#F9FAFB", borderRadius: 8, padding: spacing.sm, marginBottom: spacing.md },
  modalError: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#FEF2F2", borderRadius: 8, padding: spacing.sm, marginBottom: spacing.md },
  modalErrorText: { color: "#EF4444", fontSize: 12, flex: 1 },
  modalButtons: { flexDirection: "row", gap: spacing.md },
  successSnack: { backgroundColor: "#10B981" },
});
