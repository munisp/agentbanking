import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  StyleSheet,
  useColorScheme,
} from "react-native";

const FEATURES = [
  "Depletion prediction",
  "Top-up recommendations",
  "Risk level alerts",
];

export default function PredictiveFloatScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const colorScheme = useColorScheme();
  const isDark = colorScheme === "dark";

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await new Promise(r => setTimeout(r, 1000));
    setRefreshing(false);
  }, []);

  const filtered = FEATURES.filter((f: string) =>
    f.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <View style={[styles.center, isDark && styles.darkBg]}>
        <ActivityIndicator size="large" color="#3b82f6" />
        <Text style={[styles.loadingText, isDark && styles.darkText]}>
          Loading Float Forecast...
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, isDark && styles.darkBg]}>
      <View style={styles.header}>
        <Text style={[styles.title, isDark && styles.darkText]}>
          Float Forecast
        </Text>
      </View>

      <TextInput
        style={[styles.searchInput, isDark && styles.darkInput]}
        placeholder="Search..."
        placeholderTextColor={isDark ? "#999" : "#666"}
        value={search}
        onChangeText={setSearch}
      />

      <FlatList
        data={filtered}
        keyExtractor={(item, idx) => `${item}-${idx}`}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.featureCard, isDark && styles.darkCard]}
          >
            <Text style={[styles.featureText, isDark && styles.darkText]}>
              {item}
            </Text>
            <Text style={styles.arrow}>→</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={[styles.emptyText, isDark && styles.darkText]}>
            No results found
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  darkBg: { backgroundColor: "#1a1a1a" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  header: { padding: 16, paddingTop: 48 },
  title: { fontSize: 24, fontWeight: "bold", color: "#111" },
  darkText: { color: "#f5f5f5" },
  searchInput: {
    margin: 16,
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#ddd",
    fontSize: 16,
  },
  darkInput: { backgroundColor: "#333", borderColor: "#555", color: "#fff" },
  featureCard: {
    marginHorizontal: 16,
    marginVertical: 4,
    padding: 16,
    backgroundColor: "#fff",
    borderRadius: 8,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  darkCard: { backgroundColor: "#2a2a2a" },
  featureText: { fontSize: 16, color: "#333", flex: 1 },
  arrow: { fontSize: 18, color: "#999" },
  emptyText: {
    textAlign: "center",
    marginTop: 32,
    fontSize: 16,
    color: "#999",
  },
  loadingText: { marginTop: 12, fontSize: 16, color: "#666" },
});
