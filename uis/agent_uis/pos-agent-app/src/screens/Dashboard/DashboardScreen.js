import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    Dimensions,
    RefreshControl,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import { Card, IconButton, Text, useTheme } from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useAuth } from "../../contexts/AuthContext";
import { useSIMStatus } from "../../contexts/SIMStatusContext";
import { accountApi, ledgerApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
const SLOT_LABELS = ["Phys 1", "Phys 2", "eSIM 1", "eSIM 2"];

function rssiQuality(rssi) {
  if (rssi == null || rssi === 99) return 0;
  return Math.round((Math.min(rssi, 31) / 31) * 100);
}

function ActiveNetworkCard({ navigation }) {
  const status = useSIMStatus();

  // Orchestrator unreachable — show a greyed-out placeholder so the card is
  // always visible on the dashboard. Tapping it opens the SIM Status screen.
  if (!status) {
    return (
      <TouchableOpacity
        style={networkStyles.card}
        onPress={() => navigation.navigate("SIMStatus")}
        activeOpacity={0.8}
      >
        <View style={networkStyles.left}>
          <View style={[networkStyles.iconBg, { backgroundColor: "#F3F4F6" }]}>
            <Icon name="sim-off" size={20} color="#9CA3AF" />
          </View>
          <View>
            <Text style={networkStyles.carrier}>SIM Orchestrator</Text>
            <Text style={networkStyles.slot}>Unavailable</Text>
          </View>
        </View>
        <View style={networkStyles.right}>
          <View style={[networkStyles.signalDot, { backgroundColor: "#D1D5DB" }]} />
          <Icon name="chevron-right" size={16} color="#9CA3AF" />
        </View>
      </TouchableOpacity>
    );
  }

  const { isWifi, activeSlot, readings, transactionActive } = status;
  const active     = readings?.[activeSlot];
  const carrier    = isWifi ? "Wi-Fi" : (active?.carrier  || "—");
  const slotLabel  = isWifi ? "Wi-Fi" : (SLOT_LABELS[activeSlot] ?? `Slot ${activeSlot}`);
  const quality    = isWifi ? 80      : rssiQuality(active?.rssi);
  const score      = active?.score ?? 0;
  const scoreColor = score >= 700 ? "#10B981" : score >= 400 ? "#F59E0B" : "#EF4444";
  const dotColor   = quality >= 60 ? "#10B981" : quality >= 30 ? "#F59E0B" : "#EF4444";

  return (
    <TouchableOpacity
      style={networkStyles.card}
      onPress={() => navigation.navigate("SIMStatus")}
      activeOpacity={0.8}
    >
      <View style={networkStyles.left}>
        <View style={[networkStyles.iconBg, { backgroundColor: dotColor + "20" }]}>
          <Icon name={isWifi ? "wifi" : "sim"} size={20} color={dotColor} />
        </View>
        <View>
          <Text style={networkStyles.carrier}>{carrier}</Text>
          <Text style={networkStyles.slot}>{slotLabel}</Text>
        </View>
      </View>

      <View style={networkStyles.right}>
        {transactionActive && <View style={networkStyles.txDot} />}
        {active && !isWifi && (
          <>
            <Text style={networkStyles.stat}>{active.latencyMs} ms</Text>
            <Text style={[networkStyles.score, { color: scoreColor }]}>
              {score}/1000
            </Text>
          </>
        )}
        <View style={[networkStyles.signalDot, { backgroundColor: dotColor }]} />
        <Icon name="chevron-right" size={16} color="#9CA3AF" />
      </View>
    </TouchableOpacity>
  );
}

const networkStyles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#FFFFFF",
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    elevation: 1,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
  },
  left: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  iconBg: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: "center",
    alignItems: "center",
  },
  carrier: {
    fontSize: 14,
    fontWeight: "700",
    color: "#111827",
  },
  slot: {
    fontSize: 11,
    color: "#6B7280",
    marginTop: 1,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  stat: {
    fontSize: 12,
    color: "#6B7280",
  },
  score: {
    fontSize: 12,
    fontWeight: "700",
  },
  signalDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  txDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#F59E0B",
    marginRight: 2,
  },
});

const { width } = Dimensions.get("window");
const TILE_SIZE = (width - 56) / 3; // 3 tiles per row with padding

export default function DashboardScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const theme = useTheme();
  const { user, kycStatus, isKycVerified } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
  const [accountData, setAccountData] = useState(null);
  const [balanceVisible, setBalanceVisible] = useState(true);
  const [stats, setStats] = useState({
    balance: 0,
    todayTransactions: 0,
    totalTransactions: 0,
    activeTerminals: 0,
    pendingRequests: 0,
  });
  const [terminals, setTerminals] = useState(0);

  useEffect(() => {
    loadDashboardData();
    loadBalanceVisibility();
  }, []);

  const loadBalanceVisibility = async () => {
    try {
      const visibility = await SecureStore.getItemAsync("balanceVisible");
      if (visibility !== null) {
        setBalanceVisible(visibility === "true");
      }
    } catch (error) {
      console.error("Error loading balance visibility:", error);
    }
  };

  const toggleBalanceVisibility = async () => {
    try {
      const newVisibility = !balanceVisible;
      setBalanceVisible(newVisibility);
      await SecureStore.setItemAsync(
        "balanceVisible",
        newVisibility.toString(),
      );
    } catch (error) {
      console.error("Error saving balance visibility:", error);
    }
  };

  const loadDashboardData = async () => {
    setRefreshing(true);
    try {
      // Get the keycloak ID from secure store
      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      if (keycloakId) {
        // Fetch account data from API
        const response = await accountApi.getAccountByKeycloakId(keycloakId);
        const account = response?.account || response;

        if (account) {
          setAccountData(account);

          // Fetch transaction count
          let totalTransactionCount = 0;
          let todayTransactionCount = 0;

          try {
            const accountNumber = account.account_number;
            if (accountNumber) {
              // Fetch transactions to get count
              const txnResponse =
                await ledgerApi.getTransactionsByAccountNumber(
                  accountNumber,
                  100, // Get enough to count
                  1,
                );

              const transactions =
                txnResponse.transactions ||
                txnResponse.data ||
                txnResponse ||
                [];
              totalTransactionCount = transactions.length;

              // Count today's transactions
              const today = new Date();
              today.setHours(0, 0, 0, 0);

              todayTransactionCount = transactions.filter((txn) => {
                const txnDate = new Date(txn.created_at || txn.createdAt);
                return txnDate >= today;
              }).length;

              console.log(
                `Loaded ${totalTransactionCount} total transactions, ${todayTransactionCount} today`,
              );
            }
          } catch (txnError) {
            console.error("Error loading transactions:", txnError);
          }
          const accountNumber = account.account_number;

          const result = await ledgerApi
                      .getTransactionsByAccountNumber(accountNumber, 50, 1)
                      .then((response) => ({ accountNumber, response }))
                      .catch((err) => {
                        console.error(
                          `Failed fetching transactions for ${accountNumber}:`,
                          err,
                        );
                        return { accountNumber, response: null };
                      })
                      
          // Update stats with real data
          setStats({
            balance: account.balance || 0,
            todayTransactions: todayTransactionCount,
            totalTransactions: result.transactions || 0,
            activeTerminals: 0, // This would need a separate API call
            pendingRequests: 0, // This would need a separate API call
          });

          console.log("Account data loaded:", account);
        }
      } else {
        console.warn("No keycloak ID found");
      }
    } catch (error) {
      console.error("Error loading dashboard data:", error?.message || error);
    } finally {
      setRefreshing(false);
    }
  };

  const topActions = [
    {
      title: "Cash In",
      icon: "cash-plus",
      color: colors.primary,
      screen: "CashIn",
    },
    {
      title: "Cash Out",
      icon: "cash-minus",
      color: colors.primary,
      screen: "CashOut",
    },
    // {
    //   title: "Transfer",
    //   icon: "bank-transfer",
    //   color: colors.primary,
    //   screen: "Transfer",
    // },
    {
      title: "Float",
      icon: "water",
      color: colors.primary,
      screen: "FloatManagement",
    },
  ];

  const transactionServices = [
    {
      title: "Transfer",
      icon: "bank-transfer",
      color: colors.primary,
      screen: "Transfer",
    },
    {
      title: "Send Remit",
      icon: "send",
      color: colors.primary,
      screen: "SendRemittance",
    },
    {
      title: "Verify Remit",
      icon: "shield-check",
      color: colors.primary,
      screen: "RemittanceVerification",
    },
    // {
    //   title: "Withdraw",
    //   icon: "cash-refund",
    //   color: "#10B981",
    //   screen: "Transfer",
    // },
    {
      title: "Scan QR",
      icon: "qrcode-scan",
      color: colors.primary,
      screen: "QRScanner",
    },
    {
      title: "Generate QR",
      icon: "qrcode",
      color: colors.primary,
      screen: "QRGenerator",
    },
  ];

  const billServices = [
    // {
    //   title: "Airtime",
    //   icon: "cellphone",
    //   color: "#F59E0B",
    //   screen: "BillPayment",
    // },
    // {
    //   title: "Data",
    //   icon: "web",
    //   color: "#8B5CF6",
    //   screen: "BillPayment",
    // },
    {
      title: "Bills",
      icon: "receipt",
      color: colors.primary,
      screen: "BillPayment",
    },
  ];

  const businessServices = [
    {
      title: "Create Order",
      icon: "receipt-text",
      color: colors.primary,
      screen: "CreateOrder",
    },
    {
      title: "POS",
      icon: "credit-card-outline",
      color: colors.primary,
      screen: "POSManagement",
    },
    {
      title: "Business",
      icon: "store",
      color: colors.primary,
      screen: "BusinessManagement",
    },
    {
      title: "Inventory",
      icon: "package-variant",
      color: colors.primary,
      screen: "Inventory",
    },
    // {
    //   title: "Loans",
    //   icon: "cash-multiple",
    //   color: colors.primary,
    //   screen: "Loans",
    // },
    {
      title: "Float",
      icon: "wallet",
      color: colors.primary,
      screen: "FloatManagement",
    },
    {
      title: "Commission",
      icon: "cash-check",
      color: colors.primary,
      screen: "CommissionSettlement",
    },
    {
      title: "Loyalty",
      icon: "star-circle",
      color: colors.primary,
      screen: "Loyalty",
    },
  ];

  const settlementServices = [
    {
      title: "Settlement",
      icon: "bank-transfer",
      color: colors.primary,
      screen: "Settlement",
    },
    {
      title: "EOD Wizard",
      icon: "calculator-variant",
      color: colors.primary,
      screen: "EODWizard",
    },
    {
      title: "Reversal",
      icon: "undo-variant",
      color: colors.primary,
      screen: "Reversal",
    },
    {
      title: "Disputes",
      icon: "shield-alert",
      color: colors.primary,
      screen: "Disputes",
    },
    {
      title: "Reconcile",
      icon: "file-document-check",
      color: colors.primary,
      screen: "Reconciliation",
    },
  ];

  const otherServices = [
    {
      title: "History",
      icon: "history",
      color: colors.primary,
      screen: "Transactions",
    },
    // {
    //   title: "Network",
    //   icon: "network",
    //   color: colors.primary,
    //   screen: "NetworkStatus",
    // },
    {
      title: "Network",
      icon: "wifi-strength-4",
      color: colors.primary,
      screen: "NetworkPredictions",
    },
    {
      title: "Messages",
      icon: "message",
      color: colors.primary,
      screen: "Communication",
    },
    {
      title: "Stores",
      icon: "map-marker",
      color: colors.primary,
      screen: "StoreMap",
    },
    {
      title: "Agents",
      icon: "account-network",
      color: colors.primary,
      screen: "AgentHierarchy",
    },
    {
      title: "Accounts",
      icon: "chart-box",
      color: colors.primary,
      screen: "ChartOfAccounts",
    },
    {
      title: "Analytics",
      icon: "chart-line",
      color: colors.primary,
      screen: "Projections",
    },
    {
      title: "Profile",
      icon: "account",
      color: colors.primary,
      screen: "Profile",
    },
  ];

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: "#F3F4F6" }]}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={loadDashboardData} />
      }
    >
      {/* Welcome Header with Gradient */}
      <View style={styles.header}>
        <View style={styles.headerContent}>
          <View>
            <Text variant="bodyMedium" style={styles.greeting}>
              Welcome back,
            </Text>
            <Text variant="headlineMedium" style={styles.userName}>
              {user?.name || "Agent"}
            </Text>
          </View>
          <IconButton
            icon="bell-outline"
            iconColor="#fff"
            size={24}
            onPress={() => {}}
          />
        </View>

        {/* Balance Card */}
        <View style={styles.balanceCard}>
          <View style={styles.balanceHeader}>
            <Text variant="bodySmall" style={styles.balanceLabel}>
              Available Balance
            </Text>
            <TouchableOpacity
              onPress={toggleBalanceVisibility}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Icon
                name={balanceVisible ? "eye-outline" : "eye-off-outline"}
                size={22}
                color={colors.primary}
              />
            </TouchableOpacity>
          </View>
          <Text style={styles.balanceAmount}>
            {balanceVisible ? formatCurrency(stats.balance) : "₦••••••"}
          </Text>

          {/* Quick Stats Row */}
          <View style={styles.quickStats}>
            <View style={styles.statItem}>
              <Icon name="swap-vertical" size={16} color={colors.primary} />
              <Text style={styles.statValue}>{stats.totalTransactions}</Text>
              <Text style={styles.statLabel}>Total Txns</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Icon name="calendar-today" size={16} color={colors.primary} />
              <Text style={styles.statValue}>
                {stats.todayTransactions + 22}
              </Text>
              <Text style={styles.statLabel}>Today</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Icon name="clock-outline" size={16} color={colors.primary} />
              <Text style={styles.statValue}>{stats.pendingRequests}</Text>
              <Text style={styles.statLabel}>Pending</Text>
            </View>
          </View>
        </View>
      </View>

      {/* Active SIM / Wi-Fi indicator */}
      <ActiveNetworkCard navigation={navigation} />

      {/* KYC Verification Banner */}
      {!isKycVerified && (
        <View style={styles.kycBannerContainer}>
          <TouchableOpacity
            style={styles.kycBanner}
            onPress={() => navigation.navigate("Profile")}
            activeOpacity={0.7}
          >
            <View style={styles.kycIconContainer}>
              <Icon name="alert" size={28} color="#C2410C" />
            </View>
            <View style={styles.kycTextContainer}>
              <Text style={styles.kycTitle}>Account Not Verified</Text>
              <Text style={styles.kycSubtitle}>
                Complete KYC to unlock all features
              </Text>
            </View>
            <Icon name="chevron-right" size={20} color="#EA580C" />
          </TouchableOpacity>
        </View>
      )}

      {/* Top Actions - Cash In/Out */}
      <View style={styles.servicesContainer}>
        <View style={styles.topActionsGrid}>
          {topActions.map((action, index) => (
            <TouchableOpacity
              key={index}
              style={styles.topActionTile}
              onPress={() => navigation.navigate(action.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.topTileIcon,
                  { backgroundColor: action.color + "15" },
                ]}
              >
                <Icon name={action.icon} size={34} color={action.color} />
              </View>
              <Text
                variant="titleMedium"
                style={[styles.topTileTitle, { color: action.color }]}
              >
                {action.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Transaction Services */}
      <View style={styles.servicesContainer}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Transactions
        </Text>
        <View style={styles.tilesGrid}>
          {transactionServices.map((service, index) => (
            <TouchableOpacity
              key={index}
              style={styles.tile}
              onPress={() => navigation.navigate(service.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.tileIcon,
                  { backgroundColor: service.color + "15" },
                ]}
              >
                <Icon name={service.icon} size={32} color={service.color} />
              </View>
              <Text
                variant="bodyMedium"
                style={styles.tileTitle}
                numberOfLines={1}
              >
                {service.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Bill Payment Services */}
      <View style={styles.servicesContainer}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Bill Payments
        </Text>
        <View style={styles.tilesGrid}>
          {billServices.map((service, index) => (
            <TouchableOpacity
              key={index}
              style={styles.tile}
              onPress={() => navigation.navigate(service.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.tileIcon,
                  { backgroundColor: service.color + "15" },
                ]}
              >
                <Icon name={service.icon} size={32} color={service.color} />
              </View>
              <Text
                variant="bodyMedium"
                style={styles.tileTitle}
                numberOfLines={1}
              >
                {service.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Business Services */}
      <View style={styles.servicesContainer}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Business & Finance
        </Text>
        <View style={styles.tilesGrid}>
          {businessServices.map((service, index) => (
            <TouchableOpacity
              key={index}
              style={styles.tile}
              onPress={() => navigation.navigate(service.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.tileIcon,
                  { backgroundColor: service.color + "15" },
                ]}
              >
                <Icon name={service.icon} size={32} color={service.color} />
              </View>
              <Text
                variant="bodyMedium"
                style={styles.tileTitle}
                numberOfLines={1}
              >
                {service.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Settlement & Reconciliation */}
      <View style={styles.servicesContainer}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Settlement & Reconciliation
        </Text>
        <View style={styles.tilesGrid}>
          {settlementServices.map((service, index) => (
            <TouchableOpacity
              key={index}
              style={styles.tile}
              onPress={() => navigation.navigate(service.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.tileIcon,
                  { backgroundColor: service.color + "15" },
                ]}
              >
                <Icon name={service.icon} size={32} color={service.color} />
              </View>
              <Text
                variant="bodyMedium"
                style={styles.tileTitle}
                numberOfLines={1}
              >
                {service.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Other Services */}
      <View style={styles.servicesContainer}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          More Services
        </Text>
        <View style={styles.tilesGrid}>
          {otherServices.map((service, index) => (
            <TouchableOpacity
              key={index}
              style={styles.tile}
              onPress={() => navigation.navigate(service.screen)}
              activeOpacity={0.8}
            >
              <View
                style={[
                  styles.tileIcon,
                  { backgroundColor: service.color + "15" },
                ]}
              >
                <Icon name={service.icon} size={32} color={service.color} />
              </View>
              <Text
                variant="bodyMedium"
                style={styles.tileTitle}
                numberOfLines={1}
              >
                {service.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    paddingBottom: 30,
  },
  header: {
    marginTop: -spacing.xl,
    backgroundColor: colors.primary,
    paddingTop: spacing.xl,
    paddingBottom: spacing.xxl,
    borderBottomLeftRadius: 28,
    borderBottomRightRadius: 28,
  },
  headerContent: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  greeting: {
    color: "#fff",
    opacity: 0.95,
    fontSize: 14,
  },
  userName: {
    color: "#fff",
    fontWeight: "700",
    marginTop: 2,
  },
  balanceCard: {
    backgroundColor: colors.secondary,
    color: colors.primary,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: 20,
    padding: spacing.lg,
    elevation: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
  },
  balanceHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  balanceLabel: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "500",
  },
  balanceAmount: {
    color: colors.primary,
    fontSize: 36,
    fontWeight: "700",
    marginBottom: spacing.lg,
    letterSpacing: -0.5,
  },
  quickStats: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: "#F3F4F6",
  },
  statItem: {
    alignItems: "center",
    flex: 1,
  },
  statValue: {
    color: colors.primary,
    fontSize: 18,
    fontWeight: "700",
    marginTop: 4,
  },
  statLabel: {
    color: colors.primary,
    fontSize: 10,
    fontWeight: "500",
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 32,
    backgroundColor: "#E5E7EB",
    marginHorizontal: spacing.xs,
  },
  servicesContainer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
  },
  sectionTitle: {
    fontWeight: "700",
    marginBottom: spacing.md,
    color: colors.primary,
    fontSize: 19,
    letterSpacing: -0.3,
  },
  topActionsGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
  },
  topActionTile: {
    flex: 1,
    backgroundColor: colors.secondary,
    borderColor: colors.primary,
    color: colors.primary,
    borderRadius: 20,
    padding: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    minHeight: 115,
    borderWidth: 1,
  },
  topTileIcon: {
    width: 68,
    height: 68,
    borderRadius: 18,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  topTileTitle: {
    textAlign: "center",
    fontWeight: "600",
    fontSize: 12,
  },
  tilesGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-start",
    marginHorizontal: -8,
    gap: 10,
  },
  tile: {
    width: TILE_SIZE,
    backgroundColor: colors.secondary,
    borderColor: colors.primary,
    color: colors.primary,
    borderRadius: 18,
    padding: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    elevation: 3,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    minHeight: 115,
    borderWidth: 1,
  },
  tileIcon: {
    width: 60,
    height: 60,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  tileTitle: {
    textAlign: "center",
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
  },
  kycBannerContainer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  kycBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFF7ED",
    borderRadius: 18,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#FED7AA",
    elevation: 3,
    shadowColor: "#F59E0B",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
  },
  kycIconContainer: {
    width: 50,
    height: 50,
    borderRadius: 14,
    backgroundColor: "#FED7AA",
    justifyContent: "center",
    alignItems: "center",
  },
  kycTextContainer: {
    flex: 1,
    marginLeft: 14,
  },
  kycTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#92400E",
    letterSpacing: -0.2,
  },
  kycSubtitle: {
    fontSize: 13,
    color: "#B45309",
    marginTop: 3,
    lineHeight: 18,
  },
});
