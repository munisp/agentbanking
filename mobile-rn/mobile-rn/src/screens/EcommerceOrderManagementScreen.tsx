import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, RefreshControl, ScrollView } from 'react-native';
import { apiService } from '../services/apiService';

const STATUS_COLORS: Record<string, string> = {
  pending: '#FF9500', confirmed: '#007AFF', processing: '#AF52DE',
  shipped: '#5856D6', delivered: '#34C759', cancelled: '#FF3B30',
};
const TABS = ['all', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled'];

export default function EcommerceOrderManagementScreen({ navigation }: { navigation: any }) {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');

  const loadOrders = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiService.get('/ecommerceOrders/listOrders', { customerId: 1, limit: 50 });
      setOrders(result?.orders ?? []);
    } catch (e) {
      Alert.alert('Error', String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadOrders(); }, [loadOrders]);

  const filtered = tab === 'all' ? orders : orders.filter(o => o.status === tab);

  return (
    <View style={styles.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
        {TABS.map(t => (
          <TouchableOpacity key={t} style={[styles.tab, tab === t && styles.tabActive]} onPress={() => setTab(t)}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t === 'all' ? 'All' : t.charAt(0).toUpperCase() + t.slice(1)}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {loading ? <ActivityIndicator style={styles.loader} size="large" /> : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => String(item.id ?? item.orderNumber)}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={loadOrders} />}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const status = item.status || 'pending';
            const items = item.items as any[] || [];
            return (
              <View style={styles.orderCard}>
                <View style={styles.orderHeader}>
                  <Text style={styles.orderNumber}>#{item.orderNumber ?? item.id}</Text>
                  <View style={[styles.statusBadge, { backgroundColor: STATUS_COLORS[status] || '#999' }]}>
                    <Text style={styles.statusText}>{status}</Text>
                  </View>
                </View>
                <View style={styles.orderBody}>
                  <Text style={styles.orderTotal}>NGN {item.totalAmount ?? item.total ?? '0'}</Text>
                  <Text style={styles.orderDate}>{formatDate(item.createdAt)}</Text>
                </View>
                {items.length > 0 && (
                  <View style={styles.itemsList}>
                    {items.slice(0, 3).map((it, i) => (
                      <Text key={i} style={styles.itemLine}>{it.name ?? it.sku} x{it.quantity}</Text>
                    ))}
                    {items.length > 3 && <Text style={styles.moreItems}>+{items.length - 3} more items</Text>}
                  </View>
                )}
                <View style={styles.actions}>
                  {status === 'shipped' && (
                    <TouchableOpacity style={styles.actionBtn}><Text style={styles.actionText}>Track</Text></TouchableOpacity>
                  )}
                  {status === 'delivered' && (
                    <>
                      <TouchableOpacity style={styles.actionBtn}><Text style={styles.actionText}>Reorder</Text></TouchableOpacity>
                      <TouchableOpacity style={[styles.actionBtn, styles.actionOutline]}><Text style={styles.actionOutlineText}>Review</Text></TouchableOpacity>
                    </>
                  )}
                </View>
              </View>
            );
          }}
          ListEmptyComponent={<Text style={styles.emptyText}>No orders found</Text>}
        />
      )}
    </View>
  );
}

function formatDate(d: string) {
  try { const dt = new Date(d); return `${dt.getDate()}/${dt.getMonth() + 1}/${dt.getFullYear()}`; }
  catch { return d?.substring(0, 10) ?? ''; }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  loader: { flex: 1, justifyContent: 'center' },
  tabBar: { maxHeight: 48, borderBottomWidth: 1, borderBottomColor: '#eee' },
  tab: { paddingHorizontal: 16, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#007AFF' },
  tabText: { color: '#999', fontSize: 14 },
  tabTextActive: { color: '#007AFF', fontWeight: '600' },
  list: { padding: 8 },
  orderCard: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#eee', borderRadius: 8, padding: 12, marginBottom: 8 },
  orderHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  orderNumber: { fontWeight: 'bold', fontSize: 15 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  statusText: { color: '#fff', fontSize: 11, fontWeight: '600' },
  orderBody: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  orderTotal: { fontWeight: '600', color: '#007AFF' },
  orderDate: { color: '#999', fontSize: 12 },
  itemsList: { borderTopWidth: 1, borderTopColor: '#f0f0f0', paddingTop: 8, marginTop: 4 },
  itemLine: { fontSize: 13, color: '#666', marginBottom: 2 },
  moreItems: { fontSize: 12, color: '#999', fontStyle: 'italic' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  actionBtn: { backgroundColor: '#007AFF', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 6 },
  actionText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  actionOutline: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#007AFF' },
  actionOutlineText: { color: '#007AFF', fontSize: 13, fontWeight: '600' },
  emptyText: { textAlign: 'center', marginTop: 40, color: '#999' },
});
