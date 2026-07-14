import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
  Button,
    FlatList,
    RefreshControl,
    StyleSheet,
    View,
} from "react-native";
import { Card, Chip, FAB, Searchbar, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { disputeApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function DisputesScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const PAGE_SIZE = 10;
  const [searchQuery, setSearchQuery] = useState("");
  const [disputes, setDisputes] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDisputes();
  }, []);

  const fetchDisputes = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const response = await disputeApi.getDisputes();
      setDisputes(response.disputes || response.data || response || []);
    } catch (err) {
      console.error("Disputes fetch error:", err);
      setError(err.message || "Failed to load disputes");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchDisputes(true);
  };

  const normalizeStatus = (status) => {
    const value = (status || "raised").toLowerCase();
    if (value === "pending") return "raised";
    if (value === "under_review") return "investigating";
    return value;
  };

  const filteredDisputes = disputes.filter((dispute) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      dispute.dispute_id?.toLowerCase().includes(query) ||
      dispute.reason?.toLowerCase().includes(query) ||
      dispute.description?.toLowerCase().includes(query)
    );
  });

  const totalPages = Math.max(1, Math.ceil(filteredDisputes.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedDisputes = filteredDisputes.slice(
    (safeCurrentPage - 1) * PAGE_SIZE,
    safeCurrentPage * PAGE_SIZE,
  );

  const getStatusColor = (status) => {
    const statusLower = normalizeStatus(status);
    if (statusLower === "resolved") return "#10B981";
    if (statusLower === "escalated") return "#EF4444";
    if (statusLower === "closed") return "#6B7280";
    if (statusLower === "raised") return "#F59E0B";
    if (statusLower === "investigating") return colors.primary;
    return "#6B7280";
  };

  const renderDisputeCard = ({ item }) => (
    <Card
      style={styles.disputeCard}
      onPress={() => navigation.navigate("DisputeDetail", { dispute: item })}
    >
      <Card.Content>
        <View style={styles.disputeHeader}>
          <View style={styles.disputeInfo}>
            <Text variant="titleMedium" style={styles.disputeId}>
              {item.dispute_id}
            </Text>
            <Text variant="bodySmall" style={styles.disputeReason}>
              {item.reason}
            </Text>
          </View>
          <Chip
            mode="flat"
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(item.status) + "20" },
            ]}
            textStyle={{ color: getStatusColor(item.status), fontSize: 11 }}
          >
            {normalizeStatus(item.status).replace(/_/g, " ")}
          </Chip>
        </View>

        <Text
          variant="bodySmall"
          style={styles.disputeDescription}
          numberOfLines={2}
        >
          {item.description}
        </Text>

        <View style={styles.disputeFooter}>
          <Text variant="bodySmall" style={styles.disputeDate}>
            Created: {new Date(item.created_at).toLocaleDateString()}
          </Text>
          {item.amount && (
            <Text variant="bodySmall" style={styles.disputeAmount}>
              ₦{parseFloat(item.amount).toLocaleString()}
            </Text>
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
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search disputes..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      <FlatList
        data={paginatedDisputes}
        renderItem={renderDisputeCard}
        keyExtractor={(item) => item.dispute_id || item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="shield-alert" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No disputes found
            </Text>
          </View>
        }
      />

      {filteredDisputes.length > PAGE_SIZE && (
        <View style={styles.paginationRow}>
          <Button
            title="Previous"
            onPress={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={safeCurrentPage === 1}
          />
          <Text variant="bodySmall" style={styles.pageIndicator}>
            Page {safeCurrentPage} of {totalPages}
          </Text>
          <Button
            title="Next"
            onPress={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={safeCurrentPage >= totalPages}
          />
        </View>
      )}

      <FAB
        icon="plus"
        label="New Dispute"
        style={styles.fab}
        onPress={() => navigation.navigate("CreateDispute")}
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
  searchContainer: {
    backgroundColor: "#fff",
    padding: spacing.md,
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
  disputeCard: {
    marginBottom: spacing.md,
  },
  disputeHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  disputeInfo: {
    flex: 1,
  },
  disputeId: {
    fontWeight: "600",
  },
  disputeReason: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  statusChip: {
    height: 28,
  },
  disputeDescription: {
    color: "#374151",
    marginBottom: spacing.sm,
  },
  disputeFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  disputeDate: {
    color: "#9CA3AF",
  },
  disputeAmount: {
    fontWeight: "600",
    color: colors.primary,
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
  fab: {
    position: "absolute",
    margin: spacing.md,
    right: 0,
    bottom: 0,
  },
  paginationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
  },
  pageIndicator: {
    color: "#4B5563",
    fontWeight: "600",
  },
});
