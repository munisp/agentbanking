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

interface Dispute {
  id: string;
  type: string;
  amount: number;
  status: "open" | "investigating" | "resolved";
  date: string;
}

export default function DisputeResolutionScreen() {
  const [loading, setLoading] = useState(true);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadDisputes = useCallback(async () => {
    const data: Dispute[] = [
      {
        id: "DSP-001",
        type: "Failed Transaction",
        amount: 5000,
        status: "open",
        date: "2024-01-15",
      },
      {
        id: "DSP-002",
        type: "Wrong Amount",
        amount: 12000,
        status: "investigating",
        date: "2024-01-14",
      },
      {
        id: "DSP-003",
        type: "Duplicate Charge",
        amount: 3500,
        status: "resolved",
        date: "2024-01-12",
      },
    ];
    setDisputes(data);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    loadDisputes();
  }, [loadDisputes]);

  const statusColor = (s: string) => {
    if (s === "open") return "#ff9800";
    if (s === "investigating") return "#2196f3";
    return "#4caf50";
  };

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      <FlatList
        data={disputes}
        keyExtractor={item => item.id}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadDisputes();
            }}
          />
        }
        ListEmptyComponent={<Text style={styles.empty}>No disputes found</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card}>
            <View style={styles.row}>
              <View style={styles.info}>
                <Text style={styles.type}>{item.type}</Text>
                <Text style={styles.sub}>
                  {item.id} • {item.date}
                </Text>
              </View>
              <View
                style={[
                  styles.badge,
                  { backgroundColor: statusColor(item.status) + "20" },
                ]}
              >
                <Text
                  style={[
                    styles.badgeText,
                    { color: statusColor(item.status) },
                  ]}
                >
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>
            <Text style={styles.amount}>₦{item.amount.toLocaleString()}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  loader: { flex: 1, justifyContent: "center" },
  empty: { textAlign: "center", padding: 32, color: "#999" },
  card: { backgroundColor: "#fff", padding: 16, marginBottom: 1 },
  row: { flexDirection: "row", alignItems: "center" },
  info: { flex: 1 },
  type: { fontSize: 16, fontWeight: "600" },
  sub: { fontSize: 12, color: "#666", marginTop: 2 },
  amount: { fontSize: 14, fontWeight: "500", marginTop: 8, color: "#333" },
  badge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 10, fontWeight: "700" },
});
