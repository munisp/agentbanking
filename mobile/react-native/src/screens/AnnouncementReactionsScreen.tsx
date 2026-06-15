import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";

const API_BASE = "";

interface ScreenData {
  items: any[];
  total: number;
}

export default function AnnouncementReactionsScreen() {
  const [data, setData] = useState<ScreenData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setError(null);
      const res = await fetch(
        `${API_BASE}/api/trpc/announcementReactions.list`
      );
      const json = await res.json();
      setData(json.result?.data ?? { items: [], total: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0D7377" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={fetchData}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.title}>Announcement Reactions</Text>
        <Text style={styles.subtitle}>{data?.total ?? 0} total records</Text>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{data?.total ?? 0}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{data?.items?.length ?? 0}</Text>
          <Text style={styles.statLabel}>Loaded</Text>
        </View>
      </View>

      {data?.items?.map((item: any, index: number) => (
        <View key={item.id ?? index} style={styles.card}>
          <Text style={styles.cardTitle}>
            {item.name ?? item.reference ?? item.id ?? `Item #${index + 1}`}
          </Text>
          <Text style={styles.cardSubtitle}>
            {item.status ?? item.type ?? "\u2014"}
          </Text>
          {item.amount != null && (
            <Text style={styles.cardAmount}>
              \u20A6{Number(item.amount).toLocaleString()}
            </Text>
          )}
        </View>
      ))}

      {(!data?.items || data.items.length === 0) && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No records found</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  header: { padding: 20, backgroundColor: "#0D7377" },
  title: { fontSize: 24, fontWeight: "bold", color: "#fff" },
  subtitle: { fontSize: 14, color: "#ccc", marginTop: 4 },
  statsRow: { flexDirection: "row", padding: 12, gap: 12 },
  statCard: {
    flex: 1,
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    elevation: 2,
  },
  statValue: { fontSize: 24, fontWeight: "bold", color: "#0D7377" },
  statLabel: { fontSize: 12, color: "#666", marginTop: 4 },
  card: {
    backgroundColor: "#fff",
    marginHorizontal: 12,
    marginBottom: 8,
    borderRadius: 12,
    padding: 16,
    elevation: 1,
  },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#333" },
  cardSubtitle: { fontSize: 13, color: "#666", marginTop: 2 },
  cardAmount: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#0D7377",
    marginTop: 8,
  },
  emptyState: { padding: 40, alignItems: "center" },
  emptyText: { fontSize: 16, color: "#999" },
  loadingText: { marginTop: 12, fontSize: 14, color: "#666" },
  errorText: { fontSize: 16, color: "#e74c3c", textAlign: "center" },
  retryButton: {
    marginTop: 12,
    paddingHorizontal: 24,
    paddingVertical: 10,
    backgroundColor: "#0D7377",
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
});
