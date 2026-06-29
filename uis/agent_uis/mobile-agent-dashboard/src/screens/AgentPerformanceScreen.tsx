import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { apiClient } from '../api/APIClient';

interface AgentRow {
  id: number; agentCode: string; name: string; tier: string;
  loyaltyPoints: number; monthlyTxCount: number;
  monthlyVolume: number; monthlyCommission: number; rank: number;
}

const TIER_COLORS: Record<string, string> = {
  Bronze: '#cd7f32', Silver: '#c0c0c0', Gold: '#ffd700', Platinum: '#e5e4e2',
};

const SORT_OPTIONS = ['points', 'volume', 'transactions'] as const;

const AgentPerformanceScreen: React.FC = () => {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<typeof SORT_OPTIONS[number]>('points');

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get(
        `/analytics/agent-leaderboard?days=30&sortBy=${sortBy}&page=1&limit=50`,
      );
      setAgents(data?.agents ?? []);
    } catch (e) { console.error(e); } finally { setLoading(false); setRefreshing(false); }
  }, [sortBy]);

  useEffect(() => { load(); }, [load]);

  const filtered = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.agentCode.toLowerCase().includes(search.toLowerCase()),
  );

  const kpis = {
    total: agents.length,
    active: agents.filter(a => a.monthlyTxCount > 0).length,
    avgScore: agents.length ? Math.round(agents.reduce((s, a) => s + a.loyaltyPoints, 0) / agents.length) : 0,
    topPerformer: agents[0]?.name ?? '—',
  };

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;
  }

  return (
    <View style={s.container}>
      {/* KPI Row */}
      <View style={s.kpiRow}>
        {[
          { label: 'Total Agents', value: kpis.total },
          { label: 'Active Today', value: kpis.active },
          { label: 'Avg Score', value: kpis.avgScore },
        ].map(k => (
          <View key={k.label} style={s.kpiCard}>
            <Text style={s.kpiValue}>{k.value}</Text>
            <Text style={s.kpiLabel}>{k.label}</Text>
          </View>
        ))}
      </View>

      {/* Search */}
      <TextInput
        style={s.searchInput}
        placeholder="Search agents..."
        placeholderTextColor="#94a3b8"
        value={search}
        onChangeText={setSearch}
      />

      {/* Sort */}
      <View style={s.sortRow}>
        {SORT_OPTIONS.map(opt => (
          <TouchableOpacity
            key={opt}
            style={[s.sortChip, sortBy === opt && s.sortChipActive]}
            onPress={() => setSortBy(opt)}
          >
            <Text style={[s.sortChipText, sortBy === opt && s.sortChipTextActive]}>
              {opt.charAt(0).toUpperCase() + opt.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Agent List */}
      <FlatList
        data={filtered}
        keyExtractor={item => String(item.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#3b82f6" />}
        renderItem={({ item, index }) => (
          <View style={s.card}>
            <View style={s.rankCircle}><Text style={s.rankText}>#{index + 1}</Text></View>
            <View style={{ flex: 1 }}>
              <View style={s.cardHeader}>
                <Text style={s.agentName}>{item.name}</Text>
                <View style={[s.tierBadge, { backgroundColor: TIER_COLORS[item.tier] ?? '#64748b' }]}>
                  <Text style={s.tierText}>{item.tier}</Text>
                </View>
              </View>
              <Text style={s.agentCode}>{item.agentCode}</Text>
              <View style={s.statsRow}>
                <Text style={s.stat}>Tx: {item.monthlyTxCount}</Text>
                <Text style={s.stat}>Vol: ₦{(item.monthlyVolume / 100).toLocaleString()}</Text>
                <Text style={s.stat}>Comm: ₦{(item.monthlyCommission / 100).toLocaleString()}</Text>
              </View>
              <Text style={s.points}>{item.loyaltyPoints} pts</Text>
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={s.empty}>No agents found</Text>}
      />
    </View>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  kpiRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 12 },
  kpiCard: { flex: 1, backgroundColor: '#1e293b', borderRadius: 12, padding: 12, marginHorizontal: 4, alignItems: 'center' },
  kpiValue: { color: '#f8fafc', fontSize: 20, fontWeight: '700' },
  kpiLabel: { color: '#94a3b8', fontSize: 11, marginTop: 2 },
  searchInput: { backgroundColor: '#1e293b', borderRadius: 10, padding: 12, color: '#f8fafc', marginBottom: 8 },
  sortRow: { flexDirection: 'row', marginBottom: 12 },
  sortChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: '#1e293b', marginRight: 8 },
  sortChipActive: { backgroundColor: '#3b82f6' },
  sortChipText: { color: '#94a3b8', fontSize: 13 },
  sortChipTextActive: { color: '#fff' },
  card: { flexDirection: 'row', backgroundColor: '#1e293b', borderRadius: 12, padding: 14, marginBottom: 10, alignItems: 'center' },
  rankCircle: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#334155', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  rankText: { color: '#f8fafc', fontWeight: '700', fontSize: 14 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  agentName: { color: '#f8fafc', fontSize: 16, fontWeight: '600' },
  agentCode: { color: '#64748b', fontSize: 12, marginTop: 2 },
  tierBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  tierText: { color: '#0f172a', fontSize: 11, fontWeight: '700' },
  statsRow: { flexDirection: 'row', marginTop: 6, gap: 12 },
  stat: { color: '#94a3b8', fontSize: 12 },
  points: { color: '#fbbf24', fontSize: 13, fontWeight: '600', marginTop: 4 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40 },
});

export default AgentPerformanceScreen;
