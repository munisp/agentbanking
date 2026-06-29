import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import { accountApi } from '../services/apiService';

const WalletScreen: React.FC = () => {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [account, setAccount] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);

  useEffect(() => { loadWalletData(); }, []);

  const loadWalletData = async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true); else setLoading(true);
      setError(null);
      const keycloakId = await SecureStore.getItemAsync('keycloakId');
      if (!keycloakId) throw new Error('Session expired. Please log in again.');
      const accounts = await accountApi.getAccounts(keycloakId);
      if (accounts && accounts.length > 0) {
        setAccount(accounts[0]);
        try {
          const txHistory = await accountApi.getCashBook(keycloakId, 'all', 5);
          setTransactions(Array.isArray(txHistory) ? txHistory : []);
        } catch { setTransactions([]); }
      } else {
        throw new Error('No account found for this agent.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load wallet data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const formatNaira = (amount: number) =>
    new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 2 }).format(amount);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading wallet...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadWalletData()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadWalletData(true)} />}
    >
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Available Balance</Text>
        <Text style={styles.balanceAmount}>
          {formatNaira(parseFloat(account?.available_balance || account?.balance || 0))}
        </Text>
        <Text style={styles.accountNumber}>
          Acct: {account?.account_number || 'N/A'}
        </Text>
      </View>

      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => navigation.navigate('FloatManagement' as never)}
        >
          <Text style={styles.actionBtnText}>Float Top-Up</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnSecondary]}
          onPress={() => navigation.navigate('Transfer' as never)}
        >
          <Text style={styles.actionBtnText}>Transfer</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Transactions</Text>
        {transactions.length === 0 ? (
          <Text style={styles.emptyText}>No recent transactions</Text>
        ) : (
          transactions.map((tx: any, i: number) => (
            <View key={tx.id || i} style={styles.txRow}>
              <View style={styles.txLeft}>
                <Text style={styles.txType}>{tx.type || tx.transaction_type || 'Transaction'}</Text>
                <Text style={styles.txDate}>
                  {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : 'N/A'}
                </Text>
              </View>
              <Text style={[
                styles.txAmount,
                (tx.type === 'credit' || tx.type === 'cash_in') ? styles.credit : styles.debit,
              ]}>
                {(tx.type === 'credit' || tx.type === 'cash_in') ? '+' : '-'}
                {formatNaira(parseFloat(tx.amount || 0))}
              </Text>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
};

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  loadingText: { marginTop: 12, fontSize: 16, color: '#666' },
  errorText: { fontSize: 16, color: '#EF4444', textAlign: 'center', marginBottom: 16 },
  retryBtn: { backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: '#FFF', fontWeight: '600' },
  balanceCard: {
    margin: 16, padding: 24, backgroundColor: '#007AFF', borderRadius: 16,
    alignItems: 'center',
  },
  balanceLabel: { fontSize: 14, color: 'rgba(255,255,255,0.8)', marginBottom: 8 },
  balanceAmount: { fontSize: 36, fontWeight: 'bold', color: '#FFF', marginBottom: 4 },
  accountNumber: { fontSize: 13, color: 'rgba(255,255,255,0.7)' },
  actionsRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 12, marginBottom: 16 },
  actionBtn: {
    flex: 1, backgroundColor: '#007AFF', padding: 14,
    borderRadius: 10, alignItems: 'center',
  },
  actionBtnSecondary: { backgroundColor: '#34C759' },
  actionBtnText: { color: '#FFF', fontWeight: '600', fontSize: 14 },
  section: { margin: 16, backgroundColor: '#FFF', borderRadius: 12, padding: 16 },
  sectionTitle: { fontSize: 17, fontWeight: '600', color: '#333', marginBottom: 12 },
  emptyText: { color: '#999', textAlign: 'center', paddingVertical: 16 },
  txRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F0F0F0',
  },
  txLeft: { flex: 1 },
  txType: { fontSize: 14, fontWeight: '500', color: '#333' },
  txDate: { fontSize: 12, color: '#999', marginTop: 2 },
  txAmount: { fontSize: 15, fontWeight: '600' },
  credit: { color: '#34C759' },
  debit: { color: '#EF4444' },
});

export default WalletScreen;
