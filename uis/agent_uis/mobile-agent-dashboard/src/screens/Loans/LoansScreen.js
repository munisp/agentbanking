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
    FAB,
    Searchbar,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { loanApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function LoansScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [applications, setApplications] = useState([]);
  const [activeLoans, setActiveLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchLoans();
  }, [statusFilter]);

  const fetchLoans = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      // Fetch loan applications
      const appsResp = await loanApi.getLoanApplications(keycloakId);
      setApplications(appsResp.applications || appsResp.data || appsResp || []);

      // Fetch active loans
      try {
        const loansResp = await loanApi.getActiveLoans(keycloakId);
        setActiveLoans(loansResp.loans || loansResp.data || loansResp || []);
      } catch (loansErr) {
        console.error("Active loans fetch error:", loansErr);
      }
    } catch (err) {
      console.error("Loans fetch error:", err);
      setError(err.message || "Failed to load loans");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchLoans(true);
  };

  // Filter applications
  const filteredApplications = applications.filter((app) => {
    const matchesSearch =
      !searchQuery ||
      app.loan_application_id
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      app.loan_purpose?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      app.status?.toLowerCase() === statusFilter.toLowerCase();

    return matchesSearch && matchesStatus;
  });

  // Calculate statistics
  const stats = {
    total: applications.length,
    totalAmount: applications.reduce(
      (sum, app) => sum + (app.loan_amount || 0),
      0,
    ),
    pending: applications.filter((app) =>
      ["pending", "submitted"].includes(app.status?.toLowerCase()),
    ).length,
    approved: applications.filter((app) =>
      ["approved", "active"].includes(app.status?.toLowerCase()),
    ).length,
    activeLoansCount: activeLoans.length,
  };

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return "#10B981";
    if (statusLower === "rejected" || statusLower === "declined")
      return "#EF4444";
    if (statusLower === "pending" || statusLower === "submitted")
      return "#F59E0B";
    return "#6B7280";
  };

  const getStatusIcon = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return "check-circle";
    if (statusLower === "rejected" || statusLower === "declined")
      return "close-circle";
    if (statusLower === "pending" || statusLower === "submitted")
      return "clock-outline";
    return "information";
  };

  const renderLoanCard = ({ item }) => (
    <Card
      style={styles.loanCard}
      onPress={() => navigation.navigate("LoanDetails", { loan: item })}
    >
      <Card.Content>
        <View style={styles.loanHeader}>
          <View style={styles.loanInfo}>
            <Text variant="titleMedium" style={styles.loanId}>
              {item.loan_application_id || item.loan_id}
            </Text>
            <Text variant="bodySmall" style={styles.loanPurpose}>
              {item.loan_purpose || "Loan Purpose"}
            </Text>
          </View>
          <Chip
            mode="flat"
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(item.status) + "20" },
            ]}
            textStyle={{ color: getStatusColor(item.status), fontSize: 11 }}
            icon={getStatusIcon(item.status)}
          >
            {item.status}
          </Chip>
        </View>

        <View style={styles.loanDetails}>
          <View style={styles.detailRow}>
            <Icon name="currency-ngn" size={16} color="#6B7280" />
            <Text variant="bodySmall" style={styles.detailLabel}>
              Amount:
            </Text>
            <Text variant="bodyMedium" style={styles.detailValue}>
              ₦{parseFloat(item.loan_amount || 0).toLocaleString()}
            </Text>
          </View>

          {item.interest_rate && (
            <View style={styles.detailRow}>
              <Icon name="percent" size={16} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailLabel}>
                Interest:
              </Text>
              <Text variant="bodyMedium" style={styles.detailValue}>
                {item.interest_rate}%
              </Text>
            </View>
          )}

          {item.created_at && (
            <View style={styles.detailRow}>
              <Icon name="calendar" size={16} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailLabel}>
                Applied:
              </Text>
              <Text variant="bodyMedium" style={styles.detailValue}>
                {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
          )}
        </View>
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
      {/* Summary Cards */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.statsScroll}
        contentContainerStyle={styles.statsContent}
      >
        <Card style={styles.statCard}>
          <Card.Content style={styles.statContent}>
            <Text variant="bodySmall" style={styles.statLabel}>
              Total Applications
            </Text>
            <Text
              variant="headlineSmall"
              style={[styles.statValue, { color: colors.primary }]}
            >
              {stats.total}
            </Text>
          </Card.Content>
        </Card>

        <Card style={styles.statCard}>
          <Card.Content style={styles.statContent}>
            <Text variant="bodySmall" style={styles.statLabel}>
              Total Amount
            </Text>
            <Text
              variant="headlineSmall"
              style={[styles.statValue, { color: "#10B981" }]}
            >
              ₦{(stats.totalAmount / 1000000).toFixed(1)}M
            </Text>
          </Card.Content>
        </Card>

        <Card style={styles.statCard}>
          <Card.Content style={styles.statContent}>
            <Text variant="bodySmall" style={styles.statLabel}>
              Pending
            </Text>
            <Text
              variant="headlineSmall"
              style={[styles.statValue, { color: "#F59E0B" }]}
            >
              {stats.pending}
            </Text>
          </Card.Content>
        </Card>

        <Card style={styles.statCard}>
          <Card.Content style={styles.statContent}>
            <Text variant="bodySmall" style={styles.statLabel}>
              Active Loans
            </Text>
            <Text
              variant="headlineSmall"
              style={[styles.statValue, { color: colors.primary }]}
            >
              {stats.activeLoansCount}
            </Text>
          </Card.Content>
        </Card>
      </ScrollView>

      {/* Search and Filters */}
      <View style={styles.filtersContainer}>
        <Searchbar
          placeholder="Search loans..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filterScroll}
        >
          <Chip
            selected={statusFilter === "all"}
            onPress={() => setStatusFilter("all")}
            style={styles.filterChip}
          >
            All
          </Chip>
          <Chip
            selected={statusFilter === "pending"}
            onPress={() => setStatusFilter("pending")}
            style={styles.filterChip}
          >
            Pending
          </Chip>
          <Chip
            selected={statusFilter === "approved"}
            onPress={() => setStatusFilter("approved")}
            style={styles.filterChip}
          >
            Approved
          </Chip>
          <Chip
            selected={statusFilter === "rejected"}
            onPress={() => setStatusFilter("rejected")}
            style={styles.filterChip}
          >
            Rejected
          </Chip>
        </ScrollView>
      </View>

      {/* Loans List */}
      <FlatList
        data={filteredApplications}
        renderItem={renderLoanCard}
        keyExtractor={(item) =>
          item.loan_application_id || item.loan_id || item.id
        }
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="currency-usd-off" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No loan applications found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              Apply for your first loan to get started
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        label="Apply for Loan"
        style={styles.fab}
        onPress={() => navigation.navigate("LoanApplication")}
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
  statsScroll: {
    maxHeight: 100,
  },
  statsContent: {
    padding: spacing.md,
    paddingBottom: 0,
  },
  statCard: {
    width: 140,
    marginRight: spacing.md,
  },
  statContent: {
    alignItems: "center",
  },
  statLabel: {
    color: "#6B7280",
    textAlign: "center",
  },
  statValue: {
    fontWeight: "bold",
    marginTop: spacing.xs,
  },
  filtersContainer: {
    backgroundColor: "#fff",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  searchBar: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  filterScroll: {
    paddingHorizontal: spacing.md,
  },
  filterChip: {
    marginRight: spacing.sm,
  },
  listContent: {
    padding: spacing.md,
  },
  loanCard: {
    marginBottom: spacing.md,
  },
  loanHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.md,
  },
  loanInfo: {
    flex: 1,
  },
  loanId: {
    fontWeight: "600",
  },
  loanPurpose: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  statusChip: {
    height: 28,
  },
  loanDetails: {
    gap: spacing.sm,
  },
  detailRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  detailLabel: {
    color: "#6B7280",
  },
  detailValue: {
    fontWeight: "500",
    flex: 1,
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
  emptySubtext: {
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  fab: {
    position: "absolute",
    margin: spacing.md,
    right: 0,
    bottom: 0,
  },
});
