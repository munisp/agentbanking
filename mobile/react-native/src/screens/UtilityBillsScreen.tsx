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

export default function UtilityBillsScreen() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<Array<{ id: number; title: string }>>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    const data = Array.from({ length: 10 }, (_, i) => ({
      id: i,
      title: `Item ${i + 1}`,
    }));
    setItems(data);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      <FlatList
        data={items}
        keyExtractor={item => String(item.id)}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadData();
            }}
          />
        }
        ListEmptyComponent={<Text style={styles.empty}>No data available</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card}>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.chevron}>›</Text>
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
  card: {
    backgroundColor: "#fff",
    padding: 16,
    marginBottom: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: { fontSize: 16 },
  chevron: { fontSize: 20, color: "#999" },
});
