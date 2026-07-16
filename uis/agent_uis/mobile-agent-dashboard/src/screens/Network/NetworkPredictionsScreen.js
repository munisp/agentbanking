import React, { useEffect, useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Chip, SegmentedButtons, Text, useTheme} from "react-native-paper";
import { networkOperationsApi } from "../../services/apiService";

const TYPE_OPTIONS = [
  { label: "All", value: "all" },
  { label: "Transfer", value: "transfer" },
  { label: "Withdrawal", value: "withdrawal" },
  { label: "Airtime", value: "airtime" },
  { label: "Data", value: "data" },
  { label: "Bill", value: "bill_payment" },
];

const CHANNEL_OPTIONS = [
  { label: "All", value: "all" },
  { label: "POS", value: "pos" },
  { label: "USSD", value: "ussd" },
  { label: "Web", value: "web" },
  { label: "App", value: "app" },
];

const confidenceStyle = {
  high: { bg: "#DBEAFE", text: "#1E40AF" },
  medium: { bg: "#F3F4F6", text: "#1F2937" },
  low: { bg: "#F9FAFB", text: "#6B7280" },
};

function getRateStyle(rate) {
  if (rate >= 90) return { bg: "#DCFCE7", border: "#86EFAC", text: "#166534" };
  if (rate >= 75) return { bg: "#FEF9C3", border: "#FDE68A", text: "#854D0E" };
  if (rate >= 50) return { bg: "#FFEDD5", border: "#FDBA74", text: "#9A3412" };
  return { bg: "#FEE2E2", border: "#FCA5A5", text: "#991B1B" };
}

function formatValue(value = "") {
  return String(value)
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function NetworkPredictionsScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");

  const groupedPredictions = useMemo(() => {
    const grouped = {};
    predictions.forEach((item) => {
      if (!grouped[item.type]) grouped[item.type] = [];
      grouped[item.type].push(item);
    });
    return grouped;
  }, [predictions]);

  const loadPredictions = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const filters = {};
      if (typeFilter !== "all") filters.type = typeFilter;
      if (channelFilter !== "all") filters.channel = channelFilter;

      const response = await networkOperationsApi.getPredictions(filters);
      setPredictions(response?.predictions || []);
    } catch (error) {
      setPredictions([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadPredictions();
  }, [typeFilter, channelFilter]);

  const highCount = predictions.filter((p) => p.rate >= 90).length;
  const mediumCount = predictions.filter((p) => p.rate >= 75 && p.rate < 90).length;
  const lowCount = predictions.filter((p) => p.rate < 75).length;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadPredictions(true)} />}
    >
      <View style={styles.headerRow}>
        <View style={styles.headerTextWrap}>
          <Text style={styles.title}>Network Predictions</Text>
          <Text style={styles.subtitle}>
            Real-time success rate predictions for banking and telecom transactions
          </Text>
        </View>
        <Button mode="contained" onPress={() => loadPredictions(true)}>
          Refresh
        </Button>
      </View>

      <Card style={styles.card}>
        <Card.Title title="Filters" />
        <Card.Content>
          <Text style={styles.filterLabel}>Type</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterScrollContent}
          >
            <SegmentedButtons
              value={typeFilter}
              onValueChange={setTypeFilter}
              buttons={TYPE_OPTIONS}
              style={styles.typeSegmented}
            />
          </ScrollView>
          <Text style={[styles.filterLabel, styles.filterLabelSecond]}>Channel</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterScrollContent}
          >
            <SegmentedButtons
              value={channelFilter}
              onValueChange={setChannelFilter}
              buttons={CHANNEL_OPTIONS}
              style={styles.channelSegmented}
            />
          </ScrollView>
        </Card.Content>
      </Card>

      {loading && (
        <Card style={styles.card}>
          <Card.Content>
            <Text>Loading predictions...</Text>
          </Card.Content>
        </Card>
      )}

      {!loading && predictions.length === 0 && (
        <Card style={styles.card}>
          <Card.Title title="No Predictions Available" />
          <Card.Content>
            <Text style={styles.emptyText}>
              No data available for the selected filters. Try adjusting your filters.
            </Text>
          </Card.Content>
        </Card>
      )}

      {!loading && predictions.length > 0 && (
        <>
          {Object.entries(groupedPredictions).map(([type, items]) => (
            <Card key={type} style={styles.card}>
              <Card.Title
                title={formatValue(type)}
                subtitle={`${items.length} provider${items.length !== 1 ? "s" : ""} available`}
              />
              <Card.Content>
                {items
                  .slice()
                  .sort((a, b) => b.rate - a.rate)
                  .map((prediction, index) => {
                    const rateStyle = getRateStyle(prediction.rate || 0);
                    const confidence = confidenceStyle[prediction.confidence] || confidenceStyle.low;
                    return (
                      <View
                        key={`${type}-${prediction.name}-${index}`}
                        style={[
                          styles.predictionCard,
                          {
                            backgroundColor: rateStyle.bg,
                            borderColor: rateStyle.border,
                          },
                        ]}
                      >
                        <View style={styles.predictionHeader}>
                          <View>
                            <Text style={[styles.predictionName, { color: rateStyle.text }]}>
                              {formatValue(prediction.name)}
                            </Text>
                            <Text style={[styles.predictionChannel, { color: rateStyle.text }]}>
                              {String(prediction.channel || "").toUpperCase()}
                            </Text>
                          </View>
                          <Text style={[styles.rateText, { color: rateStyle.text }]}>
                            {prediction.status || `${prediction.rate}%`}
                          </Text>
                        </View>

                        <View style={styles.predictionMeta}>
                          <Text style={styles.metaText}>{prediction.total_txns || 0} transactions</Text>
                          <Chip
                            compact
                            style={{ backgroundColor: confidence.bg }}
                            textStyle={{ color: confidence.text }}
                          >
                            {prediction.confidence || "low"} confidence
                          </Chip>
                        </View>

                        <View style={styles.progressTrack}>
                          <View
                            style={[
                              styles.progressFill,
                              {
                                width: `${Math.max(0, Math.min(100, Number(prediction.rate || 0)))}%`,
                                backgroundColor: rateStyle.text,
                              },
                            ]}
                          />
                        </View>
                      </View>
                    );
                  })}
              </Card.Content>
            </Card>
          ))}

          <View style={styles.summaryGrid}>
            <Card style={styles.summaryCard}>
              <Card.Content>
                <Text style={styles.summaryLabel}>Total Providers</Text>
                <Text style={styles.summaryValue}>{predictions.length}</Text>
              </Card.Content>
            </Card>
            <Card style={[styles.summaryCard, { backgroundColor: "#F0FDF4" }]}>
              <Card.Content>
                <Text style={styles.summaryLabel}>High Success (&gt;90%)</Text>
                <Text style={styles.summaryValue}>{highCount}</Text>
              </Card.Content>
            </Card>
            <Card style={[styles.summaryCard, { backgroundColor: "#FEFCE8" }]}>
              <Card.Content>
                <Text style={styles.summaryLabel}>Medium (75-89%)</Text>
                <Text style={styles.summaryValue}>{mediumCount}</Text>
              </Card.Content>
            </Card>
            <Card style={[styles.summaryCard, { backgroundColor: "#FEF2F2" }]}>
              <Card.Content>
                <Text style={styles.summaryLabel}>Low (&lt;75%)</Text>
                <Text style={styles.summaryValue}>{lowCount}</Text>
              </Card.Content>
            </Card>
          </View>
        </>
      )}
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F3F4F6" },
  content: { padding: 16, gap: 12 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  headerTextWrap: { flex: 1 },
  title: { fontSize: 24, fontWeight: "700", color: "#111827" },
  subtitle: { color: "#4B5563", marginTop: 4 },
  card: { borderRadius: 12 },
  filterLabel: { fontWeight: "600", marginBottom: 6, color: "#374151" },
  filterLabelSecond: { marginTop: 10 },
  filterScrollContent: { paddingRight: 4 },
  typeSegmented: { minWidth: 620 },
  channelSegmented: { minWidth: 520 },
  emptyText: { color: "#6B7280" },
  predictionCard: {
    borderWidth: 2,
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  predictionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  predictionName: { fontSize: 16, fontWeight: "700" },
  predictionChannel: { fontSize: 11, marginTop: 2, letterSpacing: 0.5 },
  rateText: { fontSize: 18, fontWeight: "800" },
  predictionMeta: { marginTop: 8, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  metaText: { color: "#374151", fontSize: 12 },
  progressTrack: {
    marginTop: 8,
    height: 8,
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: 999,
    overflow: "hidden",
  },
  progressFill: { height: "100%" },
  summaryGrid: { gap: 8 },
  summaryCard: { borderRadius: 10 },
  summaryLabel: { fontSize: 12, color: "#4B5563" },
  summaryValue: { fontSize: 24, fontWeight: "700", color: "#111827", marginTop: 2 },
});
