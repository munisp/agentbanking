import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  ScrollView,
  Alert,
} from 'react-native';

interface StatsData {
  [key: string]: string | number;
}

interface RecordItem {
  id: number;
  status?: string;
  name?: string;
  [key: string]: any;
}

const API_BASE = 'http://localhost:3001/api/trpc';

export default function TokenizedAssetsScreen() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [items, setItems] = useState<RecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [statsRes, listRes] = await Promise.all([
        fetch(`${API_BASE}/tokenized_assets.getStats`).then(r => r.json()),
        fetch(`${API_BASE}/tokenized_assets.list?input=${encodeURIComponent(JSON.stringify({ limit: 20, offset: 0 }))}`).then(r => r.json()),
      ]);
      setStats(statsRes?.result?.data ?? {});
      setItems(listRes?.result?.data?.items ?? []);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load data');
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

  const getStatusColor = (status?: string): string => {
    switch (status?.toLowerCase()) {
      case 'active': case 'healthy': case 'verified': case 'approved': case 'confirmed':
      case 'paid': case 'online': case 'connected':
        return '#22c55e';
      case 'pending': case 'review': case 'dormant': case 'idle': case 'partial':
      case 'maintenance': case 'failover': case 'syncing':
        return '#f59e0b';
      case 'suspended': case 'failed': case 'declined': case 'rejected': case 'overdue':
      case 'defaulted': case 'offline': case 'tampered': case 'escalated': case 'lost':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.loadingText}>Loading Tokenized Assets...</Text>
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
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Tokenized Assets</Text>
        <Text style={styles.subtitle}>Fractional ownership of real estate and commodities</Text>
      </View>

      {/* Stats Grid */}
      <View style={styles.statsGrid}>
        {stats && Object.entries(stats).filter(([k]) => k !== 'lastUpdated').map(([key, value]) => (
          <View key={key} style={styles.statCard}>
            <Text style={styles.statLabel}>
              {key.replace(/([A-Z])/g, ' $1').trim()}
            </Text>
            <Text style={styles.statValue}>{String(value)}</Text>
          </View>
        ))}
      </View>

      {/* Records List */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Records ({items.length})</Text>
        {items.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No records yet</Text>
          </View>
        ) : (
          items.map((item, index) => (
            <TouchableOpacity
              key={item.id || index}
              style={styles.listItem}
              onPress={() => Alert.alert('Record', JSON.stringify(item, null, 2))}
            >
              <View style={styles.listItemLeft}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>{item.id ?? index + 1}</Text>
                </View>
                <View>
                  <Text style={styles.itemTitle}>
                    {item.name || item.partnerName || item.customerName || `Record ${index + 1}`}
                  </Text>
                  <Text style={styles.itemSubtitle}>ID: {item.id}</Text>
                </View>
              </View>
              <View style={[styles.badge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
                <Text style={[styles.badgeText, { color: getStatusColor(item.status) }]}>
                  {item.status || 'active'}
                </Text>
              </View>
            </TouchableOpacity>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  loadingText: { marginTop: 12, color: '#6b7280', fontSize: 16 },
  errorText: { color: '#ef4444', fontSize: 16, textAlign: 'center', marginBottom: 16 },
  retryButton: { backgroundColor: '#6366f1', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '600' },
  header: { padding: 20, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: '#111827' },
  subtitle: { fontSize: 14, color: '#6b7280', marginTop: 4 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', padding: 12 },
  statCard: {
    width: '48%', margin: '1%', backgroundColor: '#fff', borderRadius: 12,
    padding: 16, shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05, shadowRadius: 2, elevation: 1,
  },
  statLabel: { fontSize: 12, color: '#6b7280', textTransform: 'capitalize' },
  statValue: { fontSize: 22, fontWeight: '700', color: '#111827', marginTop: 4 },
  section: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#111827', marginBottom: 12 },
  emptyState: { alignItems: 'center', padding: 32 },
  emptyText: { color: '#9ca3af', fontSize: 16 },
  listItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#fff', padding: 14, borderRadius: 10, marginBottom: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.03,
    shadowRadius: 1, elevation: 1,
  },
  listItemLeft: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  avatar: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: '#e0e7ff',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  avatarText: { fontWeight: '700', color: '#4f46e5' },
  itemTitle: { fontSize: 15, fontWeight: '600', color: '#111827' },
  itemSubtitle: { fontSize: 12, color: '#9ca3af', marginTop: 2 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 12, fontWeight: '600' },
});
