import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Card,
    Chip,
    Searchbar,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, inventoryApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function ChartOfAccountsScreen() {
  const { colors } = useTheme();
  const safeColors = {
    ...colors,
    primary: typeof colors.primary === "string" && colors.primary.startsWith("#")
      ? colors.primary
      : "#0066FF",
  };
  const styles = makeStyles(safeColors);

  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [accounts, setAccounts] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      // Fetch agent's own account
      const agentAccountData =
        await accountApi.getAccountByKeycloakId(keycloakId);
      const agentAccount = agentAccountData.account || agentAccountData;

      // Fetch agent's stores
      const storesData = await inventoryApi.getStores(keycloakId);
      const storesList = Array.isArray(storesData.data)
        ? storesData.data
        : Array.isArray(storesData)
          ? storesData
          : [];
      setStores(storesList);

      // Fetch accounts for each store
      const storeAccountPromises = storesList.map(async (store) => {
        if (store.account_number) {
          try {
            const storeAccountData = await accountApi.getAccountByAccountNumber(
              store.account_number,
            );
            return storeAccountData.account || storeAccountData;
          } catch (err) {
            console.error(
              `Failed to fetch account for store ${store.id}:`,
              err,
            );
            return null;
          }
        }
        return null;
      });

      const storeAccounts = (await Promise.all(storeAccountPromises)).filter(
        Boolean,
      );

      // Combine agent account and store accounts
      const allAccounts = [agentAccount, ...storeAccounts].filter(Boolean);

      // Enrich accounts with owner information
      const enrichedAccounts = allAccounts.map((account) => {
        const isAgentAccount = account.keycloak_id === keycloakId;
        const store = storesList.find(
          (s) => s.account_number === account.account_number,
        );

        return {
          ...account,
          owner_type: isAgentAccount ? "agent" : store ? "store" : "unknown",
          owner_name: isAgentAccount
            ? "Agent Account"
            : store
              ? store.name
              : "Unknown",
          store_id: store?.id,
        };
      });

      setAccounts(enrichedAccounts);
    } catch (err) {
      console.error("Chart of accounts fetch error:", err);
      setError(err.message || "Failed to load accounts");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchAccounts(true);
  };

  const filteredAccounts = accounts.filter((account) => {
    // Apply type filter
    if (filterType === "agent" && account.owner_type !== "agent") return false;
    if (filterType === "store" && account.owner_type !== "store") return false;

    // Apply search
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      account.account_number?.toLowerCase().includes(query) ||
      account.owner_name?.toLowerCase().includes(query) ||
      account.account_name?.toLowerCase().includes(query)
    );
  });

  // Calculate totals
  const totals = filteredAccounts.reduce(
    (acc, account) => {
      acc.balance += parseFloat(
        account.balance || account.available_balance || 0,
      );
      acc.count += 1;
      return acc;
    },
    { balance: 0, count: 0 },
  );

  const renderAccountCard = ({ item }) => (
    <Card style={styles.accountCard}>
      <Card.Content>
        <View style={styles.accountHeader}>
          <View style={styles.iconContainer}>
            <Icon
              name={item.owner_type === "agent" ? "account" : "store"}
              size={24}
              color={colors.primary}
            />
          </View>
          <View style={styles.accountInfo}>
            <Text variant="titleMedium" style={styles.ownerName}>
              {item.owner_name}
            </Text>
            <Text variant="bodySmall" style={styles.accountNumber}>
              {item.account_number}
            </Text>
          </View>
          <Chip
            mode="flat"
            style={[
              styles.typeChip,
              {
                backgroundColor:
                  item.owner_type === "agent" ? safeColors.primary + "20" : "#10B98120",
              },
            ]}
            textStyle={{
              color: item.owner_type === "agent" ? safeColors.primary : "#10B981",
              fontSize: 11,
            }}
          >
            {item.owner_type}
          </Chip>
        </View>

        <View style={styles.balanceSection}>
          <View style={styles.balanceRow}>
            <Text variant="bodyMedium" style={styles.balanceLabel}>
              Available Balance
            </Text>
            <Text variant="titleLarge" style={styles.balanceValue}>
              ₦
              {parseFloat(
                item.balance || item.available_balance || 0,
              ).toLocaleString()}
            </Text>
          </View>

          {item.ledger_balance && (
            <View style={styles.balanceDetail}>
              <Text variant="bodySmall" style={styles.detailLabel}>
                Ledger Balance:
              </Text>
              <Text variant="bodySmall" style={styles.detailValue}>
                ₦{parseFloat(item.ledger_balance).toLocaleString()}
              </Text>
            </View>
          )}
        </View>

        {item.account_name && (
          <Text variant="bodySmall" style={styles.accountName}>
            {item.account_name}
          </Text>
        )}
      </Card.Content>
    </Card>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Summary Card */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.summaryTitle}>
            Total Balance
          </Text>
          <Text variant="displaySmall" style={styles.summaryBalance}>
            ₦{totals.balance.toLocaleString()}
          </Text>
          <Text variant="bodySmall" style={styles.summarySubtitle}>
            Across {totals.count} account{totals.count !== 1 ? "s" : ""}
          </Text>
        </Card.Content>
      </Card>

      {/* Filter */}
      <View style={styles.filterContainer}>
        <SegmentedButtons
          value={filterType}
          onValueChange={setFilterType}
          buttons={[
            { value: "all", label: "All" },
            { value: "agent", label: "Agent" },
            { value: "store", label: "Stores" },
          ]}
        />
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search accounts..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      {/* Accounts List */}
      <FlatList
        data={filteredAccounts}
        renderItem={renderAccountCard}
        keyExtractor={(item) => item.account_number || item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="bank" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No accounts found
            </Text>
          </View>
        }
      />

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  summaryCard: {
    margin: spacing.md,
    backgroundColor: colors.primary,
  },
  summaryTitle: {
    color: "#fff",
    opacity: 0.9,
  },
  summaryBalance: {
    color: "#fff",
    fontWeight: "bold",
    marginVertical: spacing.xs,
  },
  summarySubtitle: {
    color: "#fff",
    opacity: 0.8,
  },
  filterContainer: {
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  searchContainer: {
    backgroundColor: "#fff",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  searchBar: {
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  listContent: {
    padding: spacing.md,
  },
  accountCard: {
    marginBottom: spacing.md,
  },
  accountHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.sm,
  },
  accountInfo: {
    flex: 1,
  },
  ownerName: {
    fontWeight: "600",
  },
  accountNumber: {
    color: "#6B7280",
    marginTop: 2,
  },
  typeChip: {
    height: 32,
  },
  balanceSection: {
    backgroundColor: "#F9FAFB",
    padding: spacing.md,
    borderRadius: 8,
    marginBottom: spacing.sm,
  },
  balanceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  balanceLabel: {
    color: "#6B7280",
  },
  balanceValue: {
    fontWeight: "bold",
    color: "#10B981",
  },
  balanceDetail: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  detailLabel: {
    color: "#9CA3AF",
  },
  detailValue: {
    color: "#374151",
  },
  accountName: {
    color: "#6B7280",
  },
  emptyContainer: {
    padding: spacing.xl,
    alignItems: "center",
    marginTop: spacing.xxl,
  },
  emptyText: {
    marginTop: spacing.md,
    fontWeight: "600",
  },
});
