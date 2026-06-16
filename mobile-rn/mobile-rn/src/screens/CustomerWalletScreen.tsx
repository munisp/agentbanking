import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput, Alert,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface WalletTx { id: number; type: string; description: string; amount: number; status: string; createdAt: string; }

const CustomerWalletScreen: React.FC = () => {
  const [balance, setBalance] = useState(0);
  const [creditLimit, setCreditLimit] = useState(0);
  const [transactions, setTransactions] = useState<WalletTx[]>([]);
  const [stats, setStats] = useState({ totalIn: 0, totalOut: 0, count: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    try {
      const [walletRes, txRes] = await Promise.all([
        apiClient.get('/customer/wallet'),
        apiClient.get('/customer/transactions?page=1&limit=50'),
      ]);
      setBalance(walletRes.data?.balance ?? 0);
      setCreditLimit(walletRes.data?.creditLimit ?? 0);
      setTransactions(txRes.data?.transactions ?? []);
      setStats(txRes.data?.stats ?? { totalIn: 0, totalOut: 0, count: 0 });
    } catch (e) { console.error(e); } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = transactions.filter(t =>
    t.description?.toLowerCase().includes(search.toLowerCase()) ||
    t.type?.toLowerCase().includes(search.toLowerCase()),
  );

  const fmt = (v: number) => `₦${(v / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;

  return (
    <View style={s.container}>
      {/* Balance Card */}
      <View style={s.balanceCard}>
        <Text style={s.balanceLabel}>Available Balance</Text>
        <Text style={s.balanceValue}>{fmt(balance)}</Text>
        <Text style={s.creditLabel}>Credit Limit: {fmt(creditLimit)}</Text>
      </View>

      {/* Actions */}
      <View style={s.actionRow}>
        {['Top Up', 'Send', 'Freeze', 'History'].map(a => (
          <TouchableOpacity key={a} style={s.actionBtn} onPress={() => Alert.alert(a, 'Feature coming soon')}>
            <Text style={s.actionIcon}>{a === 'Top Up' ? '💰' : a === 'Send' ? '📤' : a === 'Freeze' ? '🧊' : '📋'}</Text>
            <Text style={s.actionLabel}>{a}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Stats */}
      <View style={s.statsRow}>
        <View style={s.statCard}><Text style={s.statValue}>{fmt(stats.totalIn)}</Text><Text style={s.statLabel}>Total In</Text></View>
        <View style={s.statCard}><Text style={s.statValue}>{fmt(stats.totalOut)}</Text><Text style={s.statLabel}>Total Out</Text></View>
        <View style={s.statCard}><Text style={s.statValue}>{stats.count}</Text><Text style={s.statLabel}>Tx Count</Text></View>
      </View>

      {/* Search */}
      <TextInput style={s.searchInput} placeholder="Search transactions..." placeholderTextColor="#94a3b8" value={search} onChangeText={setSearch} />

      {/* Transaction List */}
      <FlatList
        data={filtered}
        keyExtractor={item => String(item.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#3b82f6" />}
        renderItem={({ item }) => {
          const isCredit = item.amount > 0;
          return (
            <View style={s.txRow}>
              <View style={[s.txIcon, { backgroundColor: isCredit ? '#064e3b' : '#7f1d1d' }]}>
                <Text style={{ fontSize: 16 }}>{isCredit ? '↓' : '↑'}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.txDesc}>{item.description || item.type}</Text>
                <Text style={s.txDate}>{new Date(item.createdAt).toLocaleDateString()}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={[s.txAmount, { color: isCredit ? '#22c55e' : '#ef4444' }]}>{isCredit ? '+' : ''}{fmt(item.amount)}</Text>
                <View style={[s.statusBadge, { backgroundColor: item.status === 'success' ? '#064e3b' : '#7f1d1d' }]}>
                  <Text style={s.statusText}>{item.status}</Text>
                </View>
              </View>
            </View>
          );
        }}
        ListEmptyComponent={<Text style={s.empty}>No transactions</Text>}
      />
    </View>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  balanceCard: { backgroundColor: '#1e40af', borderRadius: 16, padding: 24, alignItems: 'center', marginBottom: 16 },
  balanceLabel: { color: '#93c5fd', fontSize: 14 },
  balanceValue: { color: '#fff', fontSize: 32, fontWeight: '700', marginVertical: 4 },
  creditLabel: { color: '#93c5fd', fontSize: 12 },
  actionRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 16 },
  actionBtn: { alignItems: 'center' },
  actionIcon: { fontSize: 24, marginBottom: 4 },
  actionLabel: { color: '#94a3b8', fontSize: 12 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 12 },
  statCard: { flex: 1, backgroundColor: '#1e293b', borderRadius: 10, padding: 10, marginHorizontal: 4, alignItems: 'center' },
  statValue: { color: '#f8fafc', fontSize: 14, fontWeight: '600' },
  statLabel: { color: '#64748b', fontSize: 11, marginTop: 2 },
  searchInput: { backgroundColor: '#1e293b', borderRadius: 10, padding: 12, color: '#f8fafc', marginBottom: 10 },
  txRow: { flexDirection: 'row', backgroundColor: '#1e293b', borderRadius: 10, padding: 12, marginBottom: 8, alignItems: 'center' },
  txIcon: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  txDesc: { color: '#f8fafc', fontSize: 14, fontWeight: '500' },
  txDate: { color: '#64748b', fontSize: 11, marginTop: 2 },
  txAmount: { fontSize: 14, fontWeight: '600' },
  statusBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 6, marginTop: 2 },
  statusText: { color: '#f8fafc', fontSize: 10 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40 },
});

export default CustomerWalletScreen;
