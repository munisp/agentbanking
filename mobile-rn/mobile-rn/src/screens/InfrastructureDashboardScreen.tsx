import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface ListItem {
  id: string | number;
  name?: string;
  title?: string;
  status?: string;
  type?: string;
  [key: string]: unknown;
}

const InfrastructureDashboardScreen: React.FC = () => {
  const [items, setItems] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const { data } = await apiClient.get('/dashboard/list?page=1&limit=50');
      setItems(data?.items ?? data?.data ?? []);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = useCallback(async (data: Record<string, unknown>) => {
    try {
      await apiClient.post('/dashboard/create', data);
      load(); // Refresh list
    } catch (e: any) {
      setError(e?.message ?? 'Create failed');
    }
  }, [load]);

  const handleDelete = useCallback(async (id: string | number) => {
    try {
      await apiClient.delete(`/dashboard/${id}`);
      setItems(prev => prev.filter(item => item.id !== id));
    } catch (e: any) {
      setError(e?.message ?? 'Delete failed');
    }
  }, []);


  const filtered = items.filter(item => {
    if (!search) return true;
    const q = search.toLowerCase();
    const label = (item.name ?? item.title ?? String(item.id)).toLowerCase();
    return label.includes(q);
  });

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={load}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Infrastructure Dashboard</Text>

      {/* Summary */}
      <View style={styles.summaryRow}>
        <View style={[styles.summaryCard, { backgroundColor: '#eff6ff' }]}>
          <Text style={[styles.summaryValue, { color: '#2563eb' }]}>{items.length}</Text>
          <Text style={styles.summaryLabel}>Total</Text>
        </View>
        <View style={[styles.summaryCard, { backgroundColor: '#f0fdf4' }]}>
          <Text style={[styles.summaryValue, { color: '#16a34a' }]}>{filtered.length}</Text>
          <Text style={styles.summaryLabel}>Filtered</Text>
        </View>
      </View>

      {/* Search */}
      <TextInput
        style={styles.searchInput}
        placeholder="Search..."
        value={search}
        onChangeText={setSearch}
      />

      {/* List */}
      <FlatList
        data={filtered}
        keyExtractor={(item, i) => String(item.id ?? i)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item, index }) => (
          <TouchableOpacity style={styles.card}>
            <View style={styles.cardLeft}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{index + 1}</Text>
              </View>
              <View style={styles.cardContent}>
                <Text style={styles.cardTitle}>
                  {item.name ?? item.title ?? `Item ${index + 1}`}
                </Text>
                <Text style={styles.cardSubtitle}>
                  {item.status ?? item.type ?? ''}
                </Text>
              </View>
            </View>
            <Text style={styles.chevron}>{'›'}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>No items found</Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  header: { fontSize: 22, fontWeight: '700', padding: 16, color: '#1e293b' },
  loadingText: { marginTop: 8, color: '#64748b' },
  errorText: { color: '#dc2626', fontSize: 16, textAlign: 'center', marginBottom: 12 },
  retryBtn: { backgroundColor: '#2563eb', paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '600' },
  summaryRow: { flexDirection: 'row', paddingHorizontal: 12, gap: 8 },
  summaryCard: { flex: 1, borderRadius: 12, padding: 12, alignItems: 'center' },
  summaryValue: { fontSize: 24, fontWeight: '700' },
  summaryLabel: { fontSize: 12, color: '#64748b', marginTop: 2 },
  searchInput: {
    margin: 12, padding: 12, backgroundColor: '#fff',
    borderRadius: 12, borderWidth: 1, borderColor: '#e2e8f0',
  },
  card: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#fff', marginHorizontal: 12, marginVertical: 4,
    padding: 14, borderRadius: 12,
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  cardLeft: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  avatar: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: '#e0e7ff',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  avatarText: { color: '#4f46e5', fontWeight: '600' },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: '#1e293b' },
  cardSubtitle: { fontSize: 13, color: '#64748b', marginTop: 2 },
  chevron: { fontSize: 22, color: '#94a3b8' },
  emptyText: { color: '#94a3b8', fontSize: 16 },
});

export default InfrastructureDashboardScreen;
