import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TextInput,
  TouchableOpacity, ActivityIndicator, RefreshControl,
} from 'react-native';
import { apiClient } from '../api/APIClient';

const CURRENCIES = ['NGN', 'USD', 'GBP', 'EUR', 'GHS', 'KES', 'ZAR', 'XOF'];

interface Rate { pair: string; buy: number; sell: number; spread: number; updatedAt: string; }

const MultiCurrencyScreen: React.FC = () => {
  const [rates, setRates] = useState<Rate[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [fromCcy, setFromCcy] = useState('NGN');
  const [toCcy, setToCcy] = useState('USD');
  const [amount, setAmount] = useState('1000');

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get(`/rates?base=${fromCcy}`);
      setRates(data?.rates ?? []);
    } catch (e) { console.error(e); } finally { setLoading(false); setRefreshing(false); }
  }, [fromCcy]);

  useEffect(() => { load(); }, [load]);

  const getRate = (from: string, to: string) => {
    const r = rates.find(r => r.pair === `${from}/${to}`);
    return r?.buy ?? 0;
  };

  const converted = (parseFloat(amount) || 0) * getRate(fromCcy, toCcy);

  const filtered = rates.filter(r => r.pair.toLowerCase().includes(search.toLowerCase()));

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#3b82f6" />}
    >
      {/* Converter */}
      <View style={s.converterCard}>
        <Text style={s.converterTitle}>Currency Converter</Text>
        <View style={s.converterRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.ccyLabel}>From</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
              {CURRENCIES.map(c => (
                <TouchableOpacity key={c} style={[s.ccyChip, fromCcy === c && s.ccyChipActive]} onPress={() => setFromCcy(c)}>
                  <Text style={[s.ccyChipText, fromCcy === c && s.ccyChipTextActive]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TextInput style={s.amountInput} value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="Amount" placeholderTextColor="#64748b" />
          </View>
        </View>
        <View style={s.converterRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.ccyLabel}>To</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
              {CURRENCIES.filter(c => c !== fromCcy).map(c => (
                <TouchableOpacity key={c} style={[s.ccyChip, toCcy === c && s.ccyChipActive]} onPress={() => setToCcy(c)}>
                  <Text style={[s.ccyChipText, toCcy === c && s.ccyChipTextActive]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <View style={s.resultBox}>
              <Text style={s.resultValue}>{converted.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {toCcy}</Text>
            </View>
          </View>
        </View>
        <Text style={s.rateInfo}>Rate: 1 {fromCcy} = {getRate(fromCcy, toCcy).toFixed(4)} {toCcy}</Text>
      </View>

      {/* Search */}
      <TextInput style={s.searchInput} placeholder="Search rates..." placeholderTextColor="#94a3b8" value={search} onChangeText={setSearch} />

      {/* Rate Table */}
      <View style={s.tableHeader}>
        <Text style={[s.th, { flex: 2 }]}>Pair</Text>
        <Text style={s.th}>Buy</Text>
        <Text style={s.th}>Sell</Text>
        <Text style={s.th}>Spread</Text>
      </View>
      {filtered.map(r => (
        <View key={r.pair} style={s.tableRow}>
          <Text style={[s.td, { flex: 2, fontWeight: '600' }]}>{r.pair}</Text>
          <Text style={s.td}>{r.buy.toFixed(4)}</Text>
          <Text style={s.td}>{r.sell.toFixed(4)}</Text>
          <Text style={[s.td, { color: '#fbbf24' }]}>{r.spread.toFixed(2)}%</Text>
        </View>
      ))}
    </ScrollView>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  converterCard: { backgroundColor: '#1e293b', borderRadius: 16, padding: 20, marginBottom: 16 },
  converterTitle: { color: '#f8fafc', fontSize: 18, fontWeight: '700', marginBottom: 12 },
  converterRow: { flexDirection: 'row', marginBottom: 8 },
  ccyLabel: { color: '#94a3b8', fontSize: 12, marginBottom: 4 },
  ccyChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#334155', marginRight: 6 },
  ccyChipActive: { backgroundColor: '#1d4ed8' },
  ccyChipText: { color: '#94a3b8', fontSize: 13 },
  ccyChipTextActive: { color: '#fff' },
  amountInput: { backgroundColor: '#0f172a', borderRadius: 10, padding: 12, color: '#f8fafc', fontSize: 18 },
  resultBox: { backgroundColor: '#0f172a', borderRadius: 10, padding: 12 },
  resultValue: { color: '#22c55e', fontSize: 18, fontWeight: '700' },
  rateInfo: { color: '#64748b', fontSize: 12, marginTop: 8, textAlign: 'center' },
  searchInput: { backgroundColor: '#1e293b', borderRadius: 10, padding: 12, color: '#f8fafc', marginBottom: 12 },
  tableHeader: { flexDirection: 'row', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#334155' },
  th: { flex: 1, color: '#64748b', fontSize: 12, fontWeight: '600' },
  tableRow: { flexDirection: 'row', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  td: { flex: 1, color: '#f8fafc', fontSize: 13 },
});

export default MultiCurrencyScreen;
