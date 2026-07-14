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
    Button,
    Card,
    Chip,
    Searchbar,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { commissionApi } from "../../services/apiService";
import { spacing } from "../../theme";

export default function CommissionSettlementScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [commissions, setCommissions] = useState([]);
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchCommissions();
  }, []);

  const fetchCommissions = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      // Fetch commission balance
      try {
        const balanceResponse = await commissionApi.getBalance(agentId);
        setBalance(
          parseFloat(
            balanceResponse.balance ||
              balanceResponse.available_balance ||
              balanceResponse.data?.balance ||
              0,
          ),
        );
      } catch (err) {
        console.log("Balance fetch error:", err);
      }

      // Fetch commission history
      const commissionsResponse = await commissionApi.listCommissions(agentId, {
        page: 1,
        limit: 50,
      });
      setCommissions(
        commissionsResponse.commissions ||
          commissionsResponse.data ||
          commissionsResponse ||
          [],
      );
    } catch (err) {
      console.error("Commissions fetch error:", err);
      setError(err.message || "Failed to load commissions");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchCommissions(true);
  };

  const handleWithdraw = async () => {
    if (balance <= 0) {
      setError("No available balance to withdraw");
      return;
    }

    try {
      setProcessing(true);
      const agentId = await SecureStore.getItemAsync("agentId");
      await commissionApi.requestSettlement(agentId, {
        amount: balance,
      });
      setSuccess("Settlement request submitted successfully");
      fetchCommissions();
    } catch (err) {
      console.error("Settlement request error:", err);
      setError(err.message || "Failed to request settlement");
    } finally {
      setProcessing(false);
    }
  };

  const filteredCommissions = commissions.filter((commission) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      commission.transaction_type?.toLowerCase().includes(query) ||
      commission.reference?.toLowerCase().includes(query) ||
      commission.description?.toLowerCase().includes(query)
    );
  });

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "settled" || statusLower === "completed")
      return "#10B981";
    if (statusLower === "rejected" || statusLower === "failed")
      return "#EF4444";
    if (statusLower === "pending") return "#F59E0B";
    return "#6B7280";
  };

  const renderCommissionItem = ({ item }) => (
    <Card style={styles.commissionCard}>
      <Card.Content>
        <View style={styles.commissionHeader}>
          <View style={styles.commissionInfo}>
            <Text variant="titleSmall" style={styles.commissionType}>
              {item.transaction_type || "Commission"}
            </Text>
            <Text variant="bodySmall" style={styles.commissionDate}>
              {new Date(item.created_at || item.date).toLocaleDateString()}
            </Text>
            {item.reference && (
              <Text variant="bodySmall" style={styles.commissionRef}>
                Ref: {item.reference}
              </Text>
            )}
          </View>
          <View style={styles.commissionRight}>
            <Text variant="titleMedium" style={styles.commissionAmount}>
              ₦
              {parseFloat(
                item.amount || item.commission_amount || 0,
              ).toLocaleString()}
            </Text>
            <Chip
              mode="flat"
              style={[
                styles.statusChip,
                { backgroundColor: getStatusColor(item.status) + "20" },
              ]}
              textStyle={{ color: getStatusColor(item.status), fontSize: 11 }}
            >
              {item.status || "Pending"}
            </Chip>
          </View>
        </View>
        {item.description && (
          <Text variant="bodySmall" style={styles.commissionDescription}>
            {item.description}
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
      {/* Balance Card */}
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        stickyHeaderIndices={[0]}
      >
        <View style={styles.headerSection}>
          <Card style={styles.balanceCard}>
            <Card.Content>
              <View style={styles.balanceHeader}>
                <Icon name="wallet" size={32} color="#fff" />
                <Text variant="bodyMedium" style={styles.balanceLabel}>
                  Commission Balance
                </Text>
              </View>
              <Text variant="displaySmall" style={styles.balanceAmount}>
                ₦{balance.toLocaleString()}
              </Text>
              <Button
                mode="contained"
                onPress={handleWithdraw}
                disabled={balance <= 0 || processing}
                style={styles.withdrawButton}
                loading={processing}
                icon="bank-transfer"
                buttonColor="#fff"
                textColor="#10B981"
              >
                Request Settlement
              </Button>
            </Card.Content>
          </Card>
        </View>

        {/* Search Bar */}
        <View style={styles.searchContainer}>
          <Searchbar
            placeholder="Search commissions..."
            onChangeText={setSearchQuery}
            value={searchQuery}
            style={styles.searchBar}
          />
        </View>

        {/* Commission History */}
        <View style={styles.listContainer}>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Commission History
          </Text>
          {filteredCommissions.length > 0 ? (
            <FlatList
              data={filteredCommissions}
              renderItem={renderCommissionItem}
              keyExtractor={(item, index) =>
                item.id || item.reference || index.toString()
              }
              scrollEnabled={false}
            />
          ) : (
            <View style={styles.emptyContainer}>
              <Icon name="cash-multiple" size={64} color="#D1D5DB" />
              <Text variant="bodyLarge" style={styles.emptyText}>
                No commissions found
              </Text>
              <Text variant="bodySmall" style={styles.emptySubtext}>
                Your commission earnings will appear here
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
      <Snackbar
        visible={!!success}
        onDismiss={() => setSuccess("")}
        duration={3000}
        style={{ backgroundColor: "#10B981" }}
      >
        {success}
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
  headerSection: {
    backgroundColor: "#fff",
  },
  balanceCard: {
    margin: spacing.md,
    backgroundColor: "#10B981",
  },
  balanceHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  balanceLabel: {
    color: "#fff",
    opacity: 0.9,
  },
  balanceAmount: {
    color: "#fff",
    fontWeight: "bold",
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  withdrawButton: {
    marginTop: spacing.sm,
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
  listContainer: {
    padding: spacing.md,
  },
  sectionTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
  },
  commissionCard: {
    marginBottom: spacing.md,
  },
  commissionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  commissionInfo: {
    flex: 1,
  },
  commissionType: {
    fontWeight: "600",
  },
  commissionDate: {
    color: "#6B7280",
    marginTop: 2,
  },
  commissionRef: {
    color: "#9CA3AF",
    fontSize: 11,
    marginTop: 2,
  },
  commissionRight: {
    alignItems: "flex-end",
    gap: spacing.xs,
  },
  commissionAmount: {
    fontWeight: "bold",
    color: "#10B981",
  },
  statusChip: {
    height: 24,
  },
  commissionDescription: {
    color: "#374151",
    marginTop: spacing.sm,
  },
  emptyContainer: {
    padding: spacing.xl,
    alignItems: "center",
    marginTop: spacing.xl,
  },
  emptyText: {
    marginTop: spacing.md,
    fontWeight: "600",
  },
  emptySubtext: {
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
});
