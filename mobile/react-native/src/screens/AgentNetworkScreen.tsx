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

interface Agent {
  id: string;
  name: string;
  code: string;
  status: "active" | "inactive";
  territory: string;
  transactionsToday: number;
}

export default function AgentNetworkScreen() {
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadAgents = useCallback(async () => {
    const data: Agent[] = Array.from({ length: 20 }, (_, i) => ({
      id: `ag-${i}`,
      name: `Agent ${i + 1}`,
      code: `AG-${1000 + i}`,
      status: i % 5 === 0 ? "inactive" : "active",
      territory: ["Lagos", "Abuja", "Kano", "Port Harcourt"][i % 4],
      transactionsToday: 50 + i * 10,
    }));
    setAgents(data);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const onRefresh = () => {
    setRefreshing(true);
    loadAgents();
  };

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      <FlatList
        data={agents}
        keyExtractor={item => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card}>
            <View style={styles.row}>
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor:
                      item.status === "active" ? "#4caf50" : "#999",
                  },
                ]}
              />
              <View style={styles.info}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.sub}>
                  {item.code} • {item.territory}
                </Text>
              </View>
              <View style={styles.stats}>
                <Text style={styles.txns}>{item.transactionsToday} txns</Text>
                <Text
                  style={[
                    styles.status,
                    { color: item.status === "active" ? "#4caf50" : "#999" },
                  ]}
                >
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  loader: { flex: 1, justifyContent: "center" },
  card: { backgroundColor: "#fff", padding: 16, marginBottom: 1 },
  row: { flexDirection: "row", alignItems: "center" },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  info: { flex: 1 },
  name: { fontSize: 16, fontWeight: "600" },
  sub: { fontSize: 12, color: "#666", marginTop: 2 },
  stats: { alignItems: "flex-end" },
  txns: { fontSize: 14, fontWeight: "500" },
  status: { fontSize: 10, marginTop: 2 },
});
