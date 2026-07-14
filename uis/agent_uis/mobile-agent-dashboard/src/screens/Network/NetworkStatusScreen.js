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
import { Card, Chip, SegmentedButtons, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { networkOperationsApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function NetworkStatusScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");

  useEffect(() => {
    fetchPredictions();
  }, [typeFilter, channelFilter]);

  const fetchPredictions = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const filters = {};
      if (typeFilter !== "all") filters.type = typeFilter;
      if (channelFilter !== "all") filters.channel = channelFilter;

      const res = await networkOperationsApi.getPredictions(filters);
      setPredictions(res.predictions || []);
    } catch (err) {
      console.error("Predictions fetch error:", err);
      setError(err.message || "Failed to load predictions");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchPredictions(true);
  };

  const getSuccessColor = (rate) => {
    if (rate >= 90) return "#10B981";
    if (rate >= 75) return "#F59E0B";
    if (rate >= 50) return "#F97316";
    return "#EF4444";
  };

  const getSuccessIcon = (rate) => {
    if (rate >= 90) return "check-circle";
    if (rate >= 75) return "trending-up";
    if (rate >= 50) return "trending-down";
    return "alert-circle";
  };

  const getConfidenceColor = (confidence) => {
    if (confidence === "high") {
      return typeof colors.primary === "string" && colors.primary.startsWith("#")
        ? colors.primary
        : "#0066FF";
    }
    if (confidence === "medium") return "#6B7280";
    return "#9CA3AF";
  };

  const formatType = (type) =>
    type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const formatMedium = (name) =>
    name
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  // Calculate summary stats
  const totalChannels = predictions.length;
  const avgSuccessRate =
    predictions.length > 0
      ? (
          predictions.reduce((sum, p) => sum + p.rate, 0) / predictions.length
        ).toFixed(1)
      : 0;
  const highSuccess = predictions.filter((p) => p.rate >= 90).length;
  const lowSuccess = predictions.filter((p) => p.rate < 75).length;

  const renderPredictionItem = ({ item }) => (
    <View style={styles.listRow}>
      <View style={styles.rowContent}>
        {/* Provider & Type Column */}
        <View style={styles.leftColumn}>
          <Text variant="bodyMedium" style={styles.providerName}>
            {formatMedium(item.name)}
          </Text>
          <Text variant="bodySmall" style={styles.metaText}>
            {formatType(item.type)}
          </Text>
        </View>

        {/* Channel Badge */}
        <View style={styles.centerColumn}>
          <Chip
            mode="flat"
            compact
            style={styles.channelChip}
            textStyle={styles.channelText}
          >
            {item.channel.toUpperCase()}
          </Chip>
        </View>

        {/* Success Rate */}
        <View style={styles.rateColumn}>
          <View style={styles.rateContainer}>
            <Icon
              name={getSuccessIcon(item.rate)}
              size={20}
              color={getSuccessColor(item.rate)}
            />
            <Text
              variant="titleMedium"
              style={[styles.rateText, { color: getSuccessColor(item.rate) }]}
            >
              {item.status}
            </Text>
          </View>
        </View>

        {/* Details Column */}
        <View style={styles.rightColumn}>
          <Text variant="bodySmall" style={styles.txnCount}>
            {item.total_txns.toLocaleString()} txns
          </Text>
          <Chip
            mode="flat"
            compact
            style={[
              styles.confidenceChip,
              { backgroundColor: getConfidenceColor(item.confidence) + "20" },
            ]}
            textStyle={{
              color: getConfidenceColor(item.confidence),
              fontSize: 9,
            }}
          >
            {item.confidence}
          </Chip>
        </View>
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={styles.loadingText}>
          Loading predictions...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header Stats */}
      <View style={styles.statsContainer}>
        <Card style={[styles.statCard, { backgroundColor: "#EFF6FF" }]}>
          <Card.Content style={styles.statContent}>
            <Icon name="database" size={24} color={colors.primary} />
            <Text variant="titleLarge" style={styles.statValue}>
              {totalChannels}
            </Text>
            <Text variant="bodySmall" style={styles.statLabel}>
              Active Channels
            </Text>
          </Card.Content>
        </Card>

        <Card style={[styles.statCard, { backgroundColor: "#F0FDF4" }]}>
          <Card.Content style={styles.statContent}>
            <Icon name="check-circle" size={24} color="#10B981" />
            <Text variant="titleLarge" style={styles.statValue}>
              {avgSuccessRate}%
            </Text>
            <Text variant="bodySmall" style={styles.statLabel}>
              Avg Success
            </Text>
          </Card.Content>
        </Card>

        <Card style={[styles.statCard, { backgroundColor: "#ECFDF5" }]}>
          <Card.Content style={styles.statContent}>
            <Icon name="trending-up" size={24} color="#059669" />
            <Text variant="titleLarge" style={styles.statValue}>
              {highSuccess}
            </Text>
            <Text variant="bodySmall" style={styles.statLabel}>
              High (≥90%)
            </Text>
          </Card.Content>
        </Card>

        <Card style={[styles.statCard, { backgroundColor: "#FEF2F2" }]}>
          <Card.Content style={styles.statContent}>
            <Icon name="alert-circle" size={24} color="#EF4444" />
            <Text variant="titleLarge" style={styles.statValue}>
              {lowSuccess}
            </Text>
            <Text variant="bodySmall" style={styles.statLabel}>
              Low (&lt;75%)
            </Text>
          </Card.Content>
        </Card>
      </View>

      {/* Filters */}
      <Card style={styles.filterCard}>
        <Card.Content>
          <Text variant="labelMedium" style={styles.filterLabel}>
            Transaction Type
          </Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.chipScroll}
          >
            <Chip
              selected={typeFilter === "all"}
              onPress={() => setTypeFilter("all")}
              style={styles.filterChip}
            >
              All
            </Chip>
            <Chip
              selected={typeFilter === "transfer"}
              onPress={() => setTypeFilter("transfer")}
              style={styles.filterChip}
            >
              Transfer
            </Chip>
            <Chip
              selected={typeFilter === "withdrawal"}
              onPress={() => setTypeFilter("withdrawal")}
              style={styles.filterChip}
            >
              Withdrawal
            </Chip>
            <Chip
              selected={typeFilter === "airtime"}
              onPress={() => setTypeFilter("airtime")}
              style={styles.filterChip}
            >
              Airtime
            </Chip>
            <Chip
              selected={typeFilter === "data"}
              onPress={() => setTypeFilter("data")}
              style={styles.filterChip}
            >
              Data
            </Chip>
            <Chip
              selected={typeFilter === "bill_payment"}
              onPress={() => setTypeFilter("bill_payment")}
              style={styles.filterChip}
            >
              Bill Payment
            </Chip>
          </ScrollView>

          <Text variant="labelMedium" style={styles.filterLabel}>
            Channel
          </Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.chipScroll}
          >
            <Chip
              selected={channelFilter === "all"}
              onPress={() => setChannelFilter("all")}
              style={styles.filterChip}
            >
              All
            </Chip>
            <Chip
              selected={channelFilter === "pos"}
              onPress={() => setChannelFilter("pos")}
              style={styles.filterChip}
            >
              POS
            </Chip>
            <Chip
              selected={channelFilter === "ussd"}
              onPress={() => setChannelFilter("ussd")}
              style={styles.filterChip}
            >
              USSD
            </Chip>
            <Chip
              selected={channelFilter === "web"}
              onPress={() => setChannelFilter("web")}
              style={styles.filterChip}
            >
              Web
            </Chip>
            <Chip
              selected={channelFilter === "app"}
              onPress={() => setChannelFilter("app")}
              style={styles.filterChip}
            >
              App
            </Chip>
          </ScrollView>
        </Card.Content>
      </Card>

      {/* Predictions List */}
      <View style={styles.tableContainer}>
        <View style={styles.tableHeader}>
          <Text variant="labelSmall" style={styles.headerLeft}>
            Provider / Type
          </Text>
          <Text variant="labelSmall" style={styles.headerCenter}>
            Channel
          </Text>
          <Text variant="labelSmall" style={styles.headerRate}>
            Success
          </Text>
          <Text variant="labelSmall" style={styles.headerRight}>
            Details
          </Text>
        </View>
        <FlatList
          data={predictions.sort((a, b) => b.rate - a.rate)}
          renderItem={renderPredictionItem}
          keyExtractor={(item, index) => `${item.name}-${item.type}-${index}`}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Icon name="information-outline" size={64} color="#D1D5DB" />
              <Text variant="bodyLarge" style={styles.emptyText}>
                No predictions available
              </Text>
              <Text variant="bodySmall" style={styles.emptySubtext}>
                Try adjusting your filters
              </Text>
            </View>
          }
        />
      </View>
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
    gap: spacing.sm,
  },
  loadingText: {
    color: "#6B7280",
  },
  statsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    padding: spacing.sm,
    gap: spacing.sm,
  },
  statCard: {
    flex: 1,
    minWidth: "45%",
  },
  statContent: {
    alignItems: "center",
    gap: spacing.xs,
  },
  statValue: {
    fontWeight: "bold",
  },
  statLabel: {
    color: "#6B7280",
    textAlign: "center",
  },
  filterCard: {
    margin: spacing.md,
    marginTop: 0,
  },
  filterLabel: {
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
    color: "#6B7280",
  },
  chipScroll: {
    marginBottom: spacing.sm,
  },
  filterChip: {
    marginRight: spacing.xs,
  },
  tableContainer: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    borderRadius: 8,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#F9FAFB",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
    alignItems: "center",
  },
  headerLeft: {
    flex: 2,
    fontWeight: "600",
    color: "#6B7280",
    textTransform: "uppercase",
    fontSize: 10,
  },
  headerCenter: {
    flex: 1,
    fontWeight: "600",
    color: "#6B7280",
    textTransform: "uppercase",
    fontSize: 10,
    textAlign: "center",
  },
  headerRate: {
    flex: 1.5,
    fontWeight: "600",
    color: "#6B7280",
    textTransform: "uppercase",
    fontSize: 10,
    textAlign: "center",
  },
  headerRight: {
    flex: 1.2,
    fontWeight: "600",
    color: "#6B7280",
    textTransform: "uppercase",
    fontSize: 10,
    textAlign: "right",
  },
  listContent: {
    paddingBottom: spacing.md,
  },
  listRow: {
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  rowContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  leftColumn: {
    flex: 2,
  },
  providerName: {
    fontWeight: "600",
    color: "#111827",
  },
  metaText: {
    color: "#6B7280",
    marginTop: 2,
  },
  centerColumn: {
    flex: 1,
    alignItems: "center",
  },
  channelChip: {
    height: 24,
    backgroundColor: "#F3F4F6",
  },
  channelText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#4B5563",
  },
  rateColumn: {
    flex: 1.5,
    alignItems: "center",
  },
  rateContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  rateText: {
    fontWeight: "bold",
    fontSize: 16,
  },
  rightColumn: {
    flex: 1.2,
    alignItems: "flex-end",
  },
  txnCount: {
    color: "#6B7280",
    fontSize: 11,
    marginBottom: 4,
  },
  confidenceChip: {
    height: 20,
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl * 2,
  },
  emptyText: {
    color: "#6B7280",
    marginTop: spacing.md,
  },
  emptySubtext: {
    color: "#9CA3AF",
    marginTop: spacing.xs,
  },
});
