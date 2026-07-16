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
    ProgressBar,
    SegmentedButtons,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { networkOperationsApi } from "../../services/apiService";
import { spacing, theme } from "../../theme";
export default function NetworkStatusScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");
  const [selectedMode, setSelectedMode] = useState("pos");

  // Mock predictive data based on current mode and history
  const predictiveAnalytics = {
    currentMode: selectedMode,
    predictiveScore: 92.5,
    confidence: "high",
    historicalTrend: "improving",
    recommendations: [
      {
        icon: "check-circle",
        text: "Network conditions optimal for transactions",
        severity: "success",
      },
      {
        icon: "trending-up",
        text: "Transaction success rate improved by 3.2% this week",
        severity: "info",
      },
      {
        icon: "information",
        text: "Peak performance expected between 10 AM - 2 PM",
        severity: "info",
      },
    ],
    modePerformance: {
      pos: { score: 92.5, txnCount: 847, avgResponseTime: 1.8, trend: "up" },
      ussd: {
        score: 88.3,
        txnCount: 1234,
        avgResponseTime: 2.1,
        trend: "stable",
      },
      web: { score: 95.1, txnCount: 2156, avgResponseTime: 1.2, trend: "up" },
      app: { score: 94.8, txnCount: 3421, avgResponseTime: 1.4, trend: "up" },
    },
    timeBasedPredictions: [
      { time: "6-9 AM", score: 89, volume: "Low" },
      { time: "9-12 PM", score: 94, volume: "High" },
      { time: "12-3 PM", score: 96, volume: "Peak" },
      { time: "3-6 PM", score: 91, volume: "Medium" },
      { time: "6-9 PM", score: 87, volume: "Low" },
    ],
  };

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
    if (rate >= 90) return theme.colors.success;
    if (rate >= 75) return theme.colors.warning;
    if (rate >= 50) return theme.colors.accent;
    return theme.colors.error;
  };

  const getSuccessIcon = (rate) => {
    if (rate >= 90) return "check-circle";
    if (rate >= 75) return "trending-up";
    if (rate >= 50) return "trending-down";
    return "alert-circle";
  };

  const getConfidenceColor = (confidence) => {
    if (confidence === "high") return theme.colors.primary;
    if (confidence === "medium") return theme.colors.textSecondary;
    return theme.colors.disabled;
  };

  const getTrendIcon = (trend) => {
    if (trend === "up") return "trending-up";
    if (trend === "down") return "trending-down";
    return "minus";
  };

  const getTrendColor = (trend) => {
    if (trend === "up") return theme.colors.success;
    if (trend === "down") return theme.colors.error;
    return theme.colors.textSecondary;
  };

  const getSeverityColor = (severity) => {
    if (severity === "success") return theme.colors.success;
    if (severity === "warning") return theme.colors.warning;
    if (severity === "error") return theme.colors.error;
    return theme.colors.primary;
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
      {/* Predictive Score Card */}
      <Card
        style={[
          styles.predictiveCard,
          { backgroundColor: theme.colors.primary },
        ]}
      >
        <Card.Content>
          <View style={styles.predictiveHeader}>
            <Icon name="brain" size={32} color="#FFFFFF" />
            <View style={styles.predictiveInfo}>
              <Text variant="labelSmall" style={styles.predictiveLabel}>
                Transaction Success Prediction
              </Text>
              <Text variant="headlineLarge" style={styles.predictiveScore}>
                {predictiveAnalytics.predictiveScore}%
              </Text>
            </View>
            <Chip
              mode="flat"
              style={styles.confidenceBadge}
              textStyle={styles.confidenceBadgeText}
            >
              {predictiveAnalytics.confidence.toUpperCase()} CONFIDENCE
            </Chip>
          </View>

          <View style={styles.modeSelector}>
            <Text variant="labelSmall" style={styles.modeSelectorLabel}>
              Current Mode:
            </Text>
            <View style={styles.modeButtons}>
              {Object.keys(predictiveAnalytics.modePerformance).map((mode) => (
                <Chip
                  key={mode}
                  selected={selectedMode === mode}
                  onPress={() => setSelectedMode(mode)}
                  style={[
                    styles.modeChip,
                    selectedMode === mode && styles.modeChipSelected,
                  ]}
                  textStyle={[
                    styles.modeChipText,
                    selectedMode === mode && styles.modeChipTextSelected,
                  ]}
                >
                  {mode.toUpperCase()}
                </Chip>
              ))}
            </View>
          </View>

          <View style={styles.modeStats}>
            <View style={styles.modeStatItem}>
              <Icon name="swap-horizontal" size={16} color="#FFFFFF" />
              <Text style={styles.modeStatLabel}>
                {predictiveAnalytics.modePerformance[
                  selectedMode
                ].txnCount.toLocaleString()}{" "}
                txns
              </Text>
            </View>
            <View style={styles.modeStatItem}>
              <Icon name="speedometer" size={16} color="#FFFFFF" />
              <Text style={styles.modeStatLabel}>
                {
                  predictiveAnalytics.modePerformance[selectedMode]
                    .avgResponseTime
                }
                s avg
              </Text>
            </View>
            <View style={styles.modeStatItem}>
              <Icon
                name={getTrendIcon(
                  predictiveAnalytics.modePerformance[selectedMode].trend,
                )}
                size={16}
                color="#FFFFFF"
              />
              <Text style={styles.modeStatLabel}>
                {predictiveAnalytics.modePerformance[selectedMode].trend}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Recommendations */}
      <Card style={styles.recommendationsCard}>
        <Card.Content>
          <View style={styles.recommendationsHeader}>
            <Icon name="lightbulb-on" size={20} color={theme.colors.warning} />
            <Text variant="titleSmall" style={styles.recommendationsTitle}>
              Insights & Recommendations
            </Text>
          </View>
          {predictiveAnalytics.recommendations.map((rec, index) => (
            <View key={index} style={styles.recommendationItem}>
              <Icon
                name={rec.icon}
                size={18}
                color={getSeverityColor(rec.severity)}
              />
              <Text variant="bodySmall" style={styles.recommendationText}>
                {rec.text}
              </Text>
            </View>
          ))}
        </Card.Content>
      </Card>

      {/* Time-Based Predictions */}
      <Card style={styles.timePredictionsCard}>
        <Card.Content>
          <View style={styles.sectionHeaderInline}>
            <Icon name="clock-outline" size={20} color={theme.colors.primary} />
            <Text variant="titleSmall" style={styles.sectionTitleInline}>
              Predicted Success by Time of Day
            </Text>
          </View>

          {predictiveAnalytics.timeBasedPredictions.map((pred, index) => (
            <View key={index} style={styles.timePredictionRow}>
              <View style={styles.timePredictionLeft}>
                <Text variant="bodyMedium" style={styles.timePredictionTime}>
                  {pred.time}
                </Text>
                <Chip
                  mode="flat"
                  compact
                  style={styles.volumeChip}
                  textStyle={styles.volumeChipText}
                >
                  {pred.volume}
                </Chip>
              </View>
              <View style={styles.timePredictionRight}>
                <ProgressBar
                  progress={pred.score / 100}
                  color={getSuccessColor(pred.score)}
                  style={styles.progressBar}
                />
                <Text variant="bodySmall" style={styles.timePredictionScore}>
                  {pred.score}%
                </Text>
              </View>
            </View>
          ))}
        </Card.Content>
      </Card>

      {/* Header Stats */}
      <View style={styles.statsContainer}>
        <Card style={[styles.statCard, { backgroundColor: "#EFF6FF" }]}>
          <Card.Content style={styles.statContent}>
            <Icon name="database" size={24} color={theme.colors.primary} />
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
            <Icon name="check-circle" size={24} color={theme.colors.success} />
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
            <Icon name="alert-circle" size={24} color={theme.colors.error} />
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
  predictiveCard: {
    margin: spacing.md,
    marginBottom: spacing.sm,
  },
  predictiveHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  predictiveInfo: {
    flex: 1,
  },
  predictiveLabel: {
    color: "#FFFFFF",
    opacity: 0.9,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  predictiveScore: {
    color: "#FFFFFF",
    fontWeight: "bold",
    marginTop: spacing.xs,
  },
  confidenceBadge: {
    backgroundColor: "rgba(255, 255, 255, 0.2)",
    height: 28,
  },
  confidenceBadgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "700",
  },
  modeSelector: {
    marginBottom: spacing.md,
  },
  modeSelectorLabel: {
    color: "#FFFFFF",
    opacity: 0.8,
    marginBottom: spacing.xs,
  },
  modeButtons: {
    flexDirection: "row",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
  modeChip: {
    backgroundColor: "rgba(255, 255, 255, 0.2)",
    height: 28,
  },
  modeChipSelected: {
    backgroundColor: "#FFFFFF",
  },
  modeChipText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
  },
  modeChipTextSelected: {
    color: theme.colors.primary,
  },
  modeStats: {
    flexDirection: "row",
    gap: spacing.md,
    flexWrap: "wrap",
  },
  modeStatItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  modeStatLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    opacity: 0.9,
  },
  recommendationsCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  recommendationsHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  recommendationsTitle: {
    fontWeight: "600",
  },
  recommendationItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    marginBottom: spacing.sm,
    paddingVertical: spacing.xs,
  },
  recommendationText: {
    flex: 1,
    color: theme.colors.textSecondary,
    lineHeight: 18,
  },
  timePredictionsCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionHeaderInline: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  sectionTitleInline: {
    fontWeight: "600",
  },
  timePredictionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  timePredictionLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
  },
  timePredictionTime: {
    fontWeight: "600",
    minWidth: 80,
  },
  volumeChip: {
    height: 22,
    backgroundColor: theme.colors.background,
  },
  volumeChipText: {
    fontSize: 10,
    color: theme.colors.textSecondary,
  },
  timePredictionRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
  },
  progressBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  timePredictionScore: {
    fontWeight: "600",
    minWidth: 35,
    textAlign: "right",
  },
  statsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    padding: spacing.sm,
    paddingTop: 0,
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
