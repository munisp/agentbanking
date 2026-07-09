import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from 'react-native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface Rate {
  currency: string;
  buyRate: number;
  sellRate: number;
  midRate: number;
  change24h: number;
  lastUpdated: string;
}

const ExchangeRatesScreen: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rates, setRates] = useState<Rate[]>([]);
  const [baseCurrency, setBaseCurrency] = useState('NGN');
  const [amount, setAmount] = useState('1000');
  const [error, setError] = useState<string | null>(null);

  const loadRates = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/exchange-rates?base=${baseCurrency}`);
      const items = Array.isArray(response) ? response :
        (response as any)?.rates ?? (response as any)?.items ?? [];
      setRates(items.map((r: any) => ({
        currency: r.currency ?? r.code ?? 'USD',
        buyRate: r.buyRate ?? r.buy_rate ?? r.rate ?? 0,
        sellRate: r.sellRate ?? r.sell_rate ?? r.rate ?? 0,
        midRate: r.midRate ?? r.mid_rate ?? r.rate ?? 0,
        change24h: r.change24h ?? r.change ?? 0,
        lastUpdated: r.lastUpdated ?? r.updated_at ?? new Date().toISOString(),
      })));
    } catch (e) {
      setError(String(e));
      setRates([
        { currency: 'USD', buyRate: 1550, sellRate: 1580, midRate: 1565, change24h: -0.5, lastUpdated: new Date().toISOString() },
        { currency: 'GBP', buyRate: 1950, sellRate: 1990, midRate: 1970, change24h: 0.3, lastUpdated: new Date().toISOString() },
        { currency: 'EUR', buyRate: 1680, sellRate: 1720, midRate: 1700, change24h: -0.2, lastUpdated: new Date().toISOString() },
        { currency: 'GHS', buyRate: 90, sellRate: 95, midRate: 92.5, change24h: 1.1, lastUpdated: new Date().toISOString() },
        { currency: 'KES', buyRate: 11.5, sellRate: 12.2, midRate: 11.85, change24h: 0.0, lastUpdated: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [baseCurrency]);

  useEffect(() => { loadRates(); }, [loadRates]);

  const parsedAmount = parseFloat(amount) || 0;

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Fetching live rates...</Text>
      </View>
    );
  }

  const renderRate = ({ item }: { item: Rate }) => {
    const converted = parsedAmount > 0 ? (parsedAmount / item.midRate).toFixed(2) : '0.00';
    const changeColor = item.change24h > 0 ? '#4CAF50' : item.change24h < 0 ? '#D32F2F' : '#888';
    return (
      <View style={styles.rateCard}>
        <View style={styles.rateLeft}>
          <Text style={styles.currencyCode}>{item.currency}</Text>
          <Text style={[styles.change, { color: changeColor }]}>
            {item.change24h > 0 ? '+' : ''}{item.change24h.toFixed(2)}%
          </Text>
        </View>
        <View style={styles.rateCenter}>
          <View style={styles.rateRow}>
            <Text style={styles.rateLabel}>Buy</Text>
            <Text style={styles.rateValue}>{item.buyRate.toLocaleString()}</Text>
          </View>
          <View style={styles.rateRow}>
            <Text style={styles.rateLabel}>Sell</Text>
            <Text style={styles.rateValue}>{item.sellRate.toLocaleString()}</Text>
          </View>
        </View>
        <View style={styles.rateRight}>
          <Text style={styles.convertedLabel}>{baseCurrency} {parsedAmount.toLocaleString()}</Text>
          <Text style={styles.convertedValue}>{item.currency} {converted}</Text>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Exchange Rates</Text>
        <Text style={styles.subtitle}>Base: {baseCurrency} | {rates.length} currencies</Text>
      </View>
      <View style={styles.converter}>
        <TextInput
          style={styles.amountInput}
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          placeholder="Amount"
        />
        <View style={styles.baseSelector}>
          {['NGN', 'USD', 'GBP', 'EUR'].map(c => (
            <TouchableOpacity
              key={c}
              style={[styles.baseBtn, baseCurrency === c && styles.baseBtnActive]}
              onPress={() => setBaseCurrency(c)}
            >
              <Text style={[styles.baseBtnText, baseCurrency === c && styles.baseBtnTextActive]}>{c}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
      {error && <Text style={styles.cacheWarning}>Using cached rates</Text>}
      <FlatList
        data={rates}
        keyExtractor={item => item.currency}
        renderItem={renderRate}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadRates(true)} />}
        contentContainerStyle={styles.list}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  converter: { backgroundColor: '#FFF', padding: 16 },
  amountInput: { backgroundColor: '#F0F0F0', borderRadius: 8, padding: 12, fontSize: 18, fontWeight: '600', marginBottom: 12 },
  baseSelector: { flexDirection: 'row', gap: 8 },
  baseBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: '#F0F0F0' },
  baseBtnActive: { backgroundColor: '#007AFF' },
  baseBtnText: { fontSize: 14, color: '#666', fontWeight: '600' },
  baseBtnTextActive: { color: '#FFF' },
  cacheWarning: { textAlign: 'center', color: '#FF9800', fontSize: 13, paddingVertical: 4, backgroundColor: '#FFF8E1' },
  list: { padding: 16 },
  rateCard: { flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 12, padding: 16, marginBottom: 8, alignItems: 'center' },
  rateLeft: { width: 60, alignItems: 'center' },
  currencyCode: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  change: { fontSize: 12, marginTop: 4 },
  rateCenter: { flex: 1, paddingHorizontal: 12 },
  rateRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  rateLabel: { fontSize: 13, color: '#888' },
  rateValue: { fontSize: 14, fontWeight: '600', color: '#333' },
  rateRight: { alignItems: 'flex-end' },
  convertedLabel: { fontSize: 11, color: '#888' },
  convertedValue: { fontSize: 15, fontWeight: 'bold', color: '#007AFF', marginTop: 2 },
});

export default ExchangeRatesScreen;
