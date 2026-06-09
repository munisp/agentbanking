import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  StyleSheet,
  TouchableOpacity,
} from "react-native";

interface DataItem {
  id: string;
  title: string;
  subtitle?: string;
  status?: string;
}

export default function AgentProfileScreen() {
  const [data, setData] = useState<DataItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      await new Promise(r => setTimeout(r, 500));
      setData([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <View style={s.centered}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={s.loadingText}>Loading...</Text>
      </View>
    );
  }
  if (error) {
    return (
      <View style={s.centered}>
        <Text style={s.errorText}>{error}</Text>
        <TouchableOpacity style={s.retryBtn} onPress={loadData}>
          <Text style={s.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }
  if (data.length === 0) {
    return (
      <View style={s.centered}>
        <Text style={s.emptyTitle}>No data yet</Text>
        <Text style={s.emptySub}>
          Agent profile, settings, and account management
        </Text>
      </View>
    );
  }

  return (
    <View style={s.container}>
      <View style={s.header}>
        <Text style={s.title}>Agent Profile</Text>
      </View>
      <FlatList
        data={data}
        keyExtractor={item => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card}>
            <View style={s.cardContent}>
              <Text style={s.cardTitle}>{item.title}</Text>
              {item.subtitle && <Text style={s.cardSub}>{item.subtitle}</Text>}
            </View>
            {item.status && (
              <View style={s.badge}>
                <Text style={s.badgeText}>{item.status}</Text>
              </View>
            )}
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  header: {
    padding: 16,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  title: { fontSize: 20, fontWeight: "700", color: "#1e293b" },
  loadingText: { marginTop: 12, color: "#64748b" },
  errorText: { color: "#dc2626", fontSize: 16, textAlign: "center" },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: "#2563eb",
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: "#64748b" },
  emptySub: { marginTop: 8, color: "#94a3b8", textAlign: "center" },
  card: {
    backgroundColor: "#fff",
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
  },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#1e293b" },
  cardSub: { marginTop: 4, fontSize: 14, color: "#64748b" },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: "#ecfdf5",
    borderRadius: 12,
  },
  badgeText: { fontSize: 12, fontWeight: "500", color: "#059669" },
});
