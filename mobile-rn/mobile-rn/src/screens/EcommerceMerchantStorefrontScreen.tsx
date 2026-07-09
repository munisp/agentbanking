import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert, TextInput, ActivityIndicator, RefreshControl, Image } from 'react-native';
import { apiService } from '../services/apiService';

export default function EcommerceMerchantStorefrontScreen({ navigation }: { navigation: any }) {
  const [store, setStore] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadStore = useCallback(async () => {
    try {
      setLoading(true);
      const [storeResult, prodResult] = await Promise.all([
        apiService.get('/agentStore/getMyStore', { agentId: 1 }),
        apiService.get('/ecommerceCatalog/listProducts', { limit: 50 }),
      ]);
      setStore(storeResult);
      setProducts(prodResult?.products ?? []);
    } catch (e) {
      Alert.alert('Error', String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStore(); }, [loadStore]);

  const filtered = products.filter(p =>
    !search || (p.name || '').toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      {/* Store header */}
      <View style={styles.storeHeader}>
        <Text style={styles.storeName}>{store?.storeName ?? 'My Store'}</Text>
        {store?.description && <Text style={styles.storeDesc}>{store.description}</Text>}
        <View style={styles.storeInfo}>
          {store?.averageRating && <Text style={styles.rating}>★ {store.averageRating}</Text>}
          {store?.city && <Text style={styles.location}>📍 {store.city}{store.state ? `, ${store.state}` : ''}</Text>}
          {store?.deliveryEnabled && <Text style={styles.delivery}>🚚 Delivery</Text>}
        </View>
      </View>
      {/* Search */}
      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} placeholder="Search products..." value={search} onChangeText={setSearch} />
      </View>
      {/* Products */}
      <FlatList
        data={filtered}
        numColumns={2}
        keyExtractor={(item) => item.sku || String(item.id)}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={loadStore} />}
        contentContainerStyle={styles.grid}
        renderItem={({ item }) => (
          <View style={styles.productCard}>
            <View style={styles.productImage}>
              {item.imageUrl ? <Image source={{ uri: item.imageUrl }} style={styles.image} /> : <Text style={styles.imagePlaceholder}>📦</Text>}
            </View>
            <Text style={styles.productName} numberOfLines={2}>{item.name}</Text>
            <Text style={styles.productPrice}>NGN {item.price}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No products available</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  loader: { flex: 1, justifyContent: 'center' },
  storeHeader: { padding: 16, backgroundColor: '#007AFF' },
  storeName: { color: '#fff', fontSize: 22, fontWeight: 'bold' },
  storeDesc: { color: '#ffffffcc', marginTop: 4 },
  storeInfo: { flexDirection: 'row', gap: 12, marginTop: 8 },
  rating: { color: '#FFD60A', fontWeight: '600' },
  location: { color: '#ffffffcc' },
  delivery: { color: '#ffffffcc' },
  searchRow: { padding: 12 },
  searchInput: { borderWidth: 1, borderColor: '#ddd', borderRadius: 12, paddingHorizontal: 16, height: 42 },
  grid: { padding: 8 },
  productCard: { flex: 1, margin: 4, backgroundColor: '#fff', borderRadius: 8, borderWidth: 1, borderColor: '#eee', padding: 8 },
  productImage: { height: 100, backgroundColor: '#f5f5f5', borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  image: { width: '100%', height: '100%', borderRadius: 8 },
  imagePlaceholder: { fontSize: 32 },
  productName: { fontSize: 13, fontWeight: '600', marginBottom: 4 },
  productPrice: { color: '#007AFF', fontWeight: 'bold' },
  emptyText: { textAlign: 'center', marginTop: 40, color: '#999' },
});
