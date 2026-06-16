import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, RefreshControl, ActivityIndicator, TextInput } from 'react-native';

interface StatsData { [key: string]: string | number; }
interface RecordItem { id: number; status?: string; [key: string]: any; }

const API_BASE = 'http://localhost:3001/api/trpc';

const ProjectType = ({ item }: { item: RecordItem }) => {
    const type = item.projectType || 'reforestation';
    const icons: Record<string, string> = { reforestation: '🌳', solar: '☀️', wind: '💨', cookstove: '🔥', biogas: '⛽', waste_mgmt: '♻️' };
    const colors: Record<string, string> = { reforestation: '#22c55e', solar: '#f59e0b', wind: '#38bdf8', cookstove: '#f97316', biogas: '#14b8a6', waste_mgmt: '#92400e' };
    return (<View style={{ backgroundColor: (colors[type] || '#6b7280') + '20', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, flexDirection: 'row' }}>
      <Text>{icons[type] || '🌍'} </Text><Text style={{ fontSize: 10, color: colors[type] || '#6b7280', fontWeight: '600' }}>{type.replace('_', ' ')}</Text></View>);
  };

export default function CarbonCreditsScreen() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [items, setItems] = useState<RecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [statsRes, listRes] = await Promise.all([
        fetch(`${API_BASE}/carbon_credits.getStats`).then(r => r.json()),
        fetch(`${API_BASE}/carbon_credits.list?input=${encodeURIComponent(JSON.stringify({ limit: 20, offset: 0 }))}`).then(r => r.json()),
      ]);
      setStats(statsRes?.result?.data ?? {});
      setItems(listRes?.result?.data?.items ?? []);
      setError('');
    } catch (e: any) { setError(e.message || 'Failed to load'); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  const onRefresh = useCallback(() => { setRefreshing(true); loadData(); }, [loadData]);

  const filtered = search ? items.filter(item => Object.values(item).some(v => String(v).toLowerCase().includes(search.toLowerCase()))) : items;

  const getStatusColor = (s?: string): string => {
    const m: Record<string, string> = { active: '#22c55e', pending: '#f59e0b', suspended: '#ef4444', completed: '#3b82f6', failed: '#ef4444', online: '#22c55e', offline: '#ef4444', verified: '#22c55e', overdue: '#ef4444', connected: '#22c55e', processed: '#22c55e' };
    return m[s || ''] || '#6b7280';
  };

  if (loading) return (<View style={styles.center}><ActivityIndicator size="large" color="#3b82f6" /><Text style={styles.loadingText}>Loading Carbon Credits...</Text></View>);
  if (error) return (<View style={styles.center}><Text style={styles.errorText}>⚠️ {error}</Text><TouchableOpacity onPress={loadData} style={styles.retryBtn}><Text style={styles.retryText}>Retry</Text></TouchableOpacity></View>);

  return (
    <FlatList
      data={filtered}
      keyExtractor={item => String(item.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      ListHeaderComponent={
        <View>
          <View style={styles.header}>
            <Text style={styles.title}>Carbon Credits</Text>
            <Text style={styles.subtitle}>Carbon credit marketplace</Text>
          </View>
          <View style={styles.statsGrid}>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>🌳</Text>
            <Text style={styles.statLabel}>Projects</Text>
            <Text style={styles.statValue}>{stats?.totalProjects ?? '—'}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>📜</Text>
            <Text style={styles.statLabel}>Issued</Text>
            <Text style={styles.statValue}>{stats?.creditsIssued ?? '—'}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>✅</Text>
            <Text style={styles.statLabel}>Retired</Text>
            <Text style={styles.statValue}>{stats?.creditsRetired ?? '—'}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>💰</Text>
            <Text style={styles.statLabel}>Market Volume</Text>
            <Text style={styles.statValue}>₦{stats?.marketVolume ?? '—'}</Text>
          </View>
          </View>
          <View style={styles.searchWrap}>
            <TextInput style={styles.searchInput} placeholder="Search records..." value={search} onChangeText={setSearch} placeholderTextColor="#9ca3af" />
          </View>
          <Text style={styles.sectionTitle}>Records ({filtered.length})</Text>
        </View>
      }
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.idBadge}><Text style={styles.idText}>#{item.id}</Text></View>
            <Text style={styles.cardTitle} numberOfLines={1}>{item.projectName || `Record #${item.id}`}</Text>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
              <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>{(item.status || '—').toUpperCase()}</Text>
            </View>
          </View>
          <View style={styles.cardBody}>
            <ProjectType item={item} />
          </View>
        </View>
      )}
      ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyText}>No records found</Text></View>}
      contentContainerStyle={styles.list}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  loadingText: { marginTop: 12, color: '#6b7280' },
  errorText: { fontSize: 16, color: '#ef4444', textAlign: 'center', marginBottom: 16 },
  retryBtn: { backgroundColor: '#3b82f6', paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '600' },
  header: { padding: 16 },
  title: { fontSize: 22, fontWeight: '800', color: '#111' },
  subtitle: { fontSize: 13, color: '#6b7280', marginTop: 4 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12 },
  statCard: { width: '48%', backgroundColor: '#f9fafb', borderRadius: 12, padding: 12, margin: '1%', borderWidth: 1, borderColor: '#e5e7eb' },
  statIcon: { fontSize: 18 },
  statLabel: { fontSize: 11, color: '#6b7280', marginTop: 4 },
  statValue: { fontSize: 20, fontWeight: '800', color: '#111', marginTop: 2 },
  searchWrap: { paddingHorizontal: 16, paddingVertical: 8 },
  searchInput: { backgroundColor: '#f3f4f6', borderRadius: 12, paddingHorizontal: 16, paddingVertical: 10, fontSize: 14, borderWidth: 1, borderColor: '#e5e7eb' },
  sectionTitle: { fontSize: 16, fontWeight: '700', paddingHorizontal: 16, paddingBottom: 8, color: '#374151' },
  card: { backgroundColor: '#fff', marginHorizontal: 16, marginBottom: 8, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#e5e7eb', shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2, elevation: 1 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  idBadge: { backgroundColor: '#ede9fe', width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginRight: 8 },
  idText: { fontSize: 11, fontWeight: '700', color: '#7c3aed' },
  cardTitle: { flex: 1, fontSize: 14, fontWeight: '600', color: '#111' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 12 },
  statusText: { fontSize: 10, fontWeight: '700' },
  cardBody: { paddingTop: 4 },
  empty: { padding: 40, alignItems: 'center' },
  emptyText: { color: '#9ca3af', fontSize: 14 },
  list: { paddingBottom: 32 },
});
