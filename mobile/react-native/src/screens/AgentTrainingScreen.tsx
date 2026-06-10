import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';

interface ItemType {
  id: string;
  module: string;
  progress: string;
  certification: string;
  score: string;
}

/** Training modules and certifications */
export default function AgentTrainingScreen() {
  const [items, setItems] = useState<ItemType[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      await new Promise((r) => setTimeout(r, 500));
      setItems([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0D7C66" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadData}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Agent Training</Text>
        <Text style={styles.headerSubtitle}>{items.length} items</Text>
      </View>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No data available</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{item.module}</Text>
              <Text style={styles.cardBadge}>{item.certification}</Text>
            </View>
            <Text style={styles.cardSubtitle}>{item.progress}</Text>
            <Text style={styles.cardMeta}>{item.score}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  header: { backgroundColor: '#0D7C66', padding: 20, paddingTop: 48 },
  headerTitle: { color: '#fff', fontSize: 24, fontWeight: 'bold' },
  headerSubtitle: { color: 'rgba(255,255,255,0.8)', fontSize: 14, marginTop: 4 },
  loadingText: { marginTop: 12, color: '#666' },
  errorText: { color: '#d32f2f', fontSize: 16, textAlign: 'center', marginBottom: 16 },
  retryButton: { backgroundColor: '#0D7C66', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '600' },
  empty: { padding: 40, alignItems: 'center' },
  emptyText: { color: '#999', fontSize: 16 },
  card: { backgroundColor: '#fff', marginHorizontal: 16, marginVertical: 6, padding: 16, borderRadius: 12, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: '#333' },
  cardBadge: { fontSize: 12, color: '#0D7C66', fontWeight: '600' },
  cardSubtitle: { fontSize: 14, color: '#666', marginTop: 4 },
  cardMeta: { fontSize: 12, color: '#999', marginTop: 4 },
});
