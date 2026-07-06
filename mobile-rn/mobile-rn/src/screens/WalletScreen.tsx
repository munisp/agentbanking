import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface WalletBalance {
  currency: string;
  balance: number;
  available: number;
  pending: number;
}

interface RecentTx {
  id: string;
  type: string;
  amount: number;
  currency: string;
  description: string;
  createdAt: string;
  status: string;
}

const WalletScreen: React.FC = () => {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [balances, setBalances] = useState<WalletBalance[]>([]);
  const [recentTxs, setRecentTxs] = useState<RecentTx[]>([]);

  const loadWallet = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const [balRes, txRes] = await Promise.all([
        apiClient.get('/wallet/balances'),
        apiClient.get('/wallet/transactions?limit=5'),
      ]);
      const bals = Array.isArray(balRes) ? balRes :
        (balRes as any)?.balances ?? (balRes as any)?.items ?? [];
      setBalances(bals.map((b: any) => ({
        currency: b.currency ?? 'NGN',
        balance: b.balance ?? b.amount ?? 0,
        available: b.available ?? b.availableBalance ?? b.balance ?? 0,
        pending: b.pending ?? b.pendingBalance ?? 0,
      })));
      const txs = Array.isArray(txRes) ? txRes :
        (txRes as any)?.transactions ?? (txRes as any)?.items ?? [];
      setRecentTxs(txs.slice(0, 5).map((t: any) => ({
        id: t.id ?? String(Math.random()),
        type: t.type ?? 'transfer',
        amount: t.amount ?? 0,
        currency: t.currency ?? 'NGN',
        description: t.description ?? t.narration ?? '',
        createdAt: t.createdAt ?? t.created_at ?? new Date().toISOString(),
        status: t.status ?? 'completed',
      })));
    } catch (e) {
      console.error('Failed to load wallet:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadWallet(); }, [loadWallet]);

  const primaryBalance = balances.find(b => b.currency === 'NGN') ?? balances[0];

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading wallet...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadWallet(true)} />}
    >
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Available Balance</Text>
        <Text style={styles.balanceAmount}>
          {primaryBalance?.currency ?? 'NGN'} {(primaryBalance?.available ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </Text>
        {(primaryBalance?.pending ?? 0) > 0 && (
          <Text style={styles.pendingText}>Pending: {primaryBalance?.currency} {primaryBalance?.pending.toLocaleString()}</Text>
        )}
        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.actionBtn} onPress={() => (navigation as any).navigate('SendMoney')}>
            <Text style={styles.actionText}>Send</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionBtn} onPress={() => (navigation as any).navigate('ReceiveMoney')}>
            <Text style={styles.actionText}>Receive</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionBtn} onPress={() => (navigation as any).navigate('TopUp')}>
            <Text style={styles.actionText}>Top Up</Text>
          </TouchableOpacity>
        </View>
      </View>

      {balances.length > 1 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Other Balances</Text>
          {balances.filter(b => b.currency !== 'NGN').map(b => (
            <View key={b.currency} style={styles.otherBalance}>
              <Text style={styles.otherCurrency}>{b.currency}</Text>
              <Text style={styles.otherAmount}>{b.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Recent Transactions</Text>
          <TouchableOpacity onPress={() => (navigation as any).navigate('Transactions')}>
            <Text style={styles.viewAll}>View All</Text>
          </TouchableOpacity>
        </View>
        {recentTxs.length === 0 ? (
          <Text style={styles.empty}>No recent transactions</Text>
        ) : recentTxs.map(tx => (
          <View key={tx.id} style={styles.txRow}>
            <View style={styles.txInfo}>
              <Text style={styles.txDesc}>{tx.description || tx.type}</Text>
              <Text style={styles.txDate}>{new Date(tx.createdAt).toLocaleDateString()}</Text>
            </View>
            <Text style={[styles.txAmount, tx.type === 'credit' ? styles.credit : styles.debit]}>
              {tx.type === 'credit' ? '+' : '-'}{tx.currency} {tx.amount.toLocaleString()}
            </Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  balanceCard: { backgroundColor: '#007AFF', padding: 24, margin: 16, borderRadius: 16 },
  balanceLabel: { color: '#B3D9FF', fontSize: 14 },
  balanceAmount: { color: '#FFF', fontSize: 32, fontWeight: 'bold', marginTop: 8 },
  pendingText: { color: '#B3D9FF', fontSize: 13, marginTop: 4 },
  actionRow: { flexDirection: 'row', marginTop: 20, gap: 12 },
  actionBtn: { flex: 1, backgroundColor: 'rgba(255,255,255,0.2)', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  actionText: { color: '#FFF', fontWeight: '600', fontSize: 15 },
  section: { backgroundColor: '#FFF', marginHorizontal: 16, marginBottom: 16, borderRadius: 12, padding: 16 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#333', marginBottom: 12 },
  viewAll: { color: '#007AFF', fontSize: 14 },
  otherBalance: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  otherCurrency: { fontSize: 16, fontWeight: '600', color: '#333' },
  otherAmount: { fontSize: 16, color: '#333' },
  txRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  txInfo: { flex: 1 },
  txDesc: { fontSize: 15, color: '#333' },
  txDate: { fontSize: 12, color: '#999', marginTop: 2 },
  txAmount: { fontSize: 16, fontWeight: '600' },
  credit: { color: '#4CAF50' },
  debit: { color: '#D32F2F' },
  empty: { textAlign: 'center', color: '#999', fontSize: 14, paddingVertical: 20 },
});

export default WalletScreen;
