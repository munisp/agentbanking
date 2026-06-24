import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert, TextInput, ActivityIndicator, RefreshControl, Image, ScrollView } from 'react-native';
import { apiService } from '../services/apiService';

interface Product {
  id: number;
  sku: string;
  name: string;
  price: string;
  imageUrl?: string;
  categoryId: number;
  merchantId: number;
  description?: string;
}

interface Category { id: number; name: string; slug: string; }

export default function EcommerceProductCatalogScreen({ navigation }: { navigation: any }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [prodResult, catResult] = await Promise.all([
        apiService.get('/ecommerceCatalog/listProducts', { limit: 50 }),
        apiService.get('/ecommerceCatalog/listCategories'),
      ]);
      setProducts(prodResult?.products ?? []);
      setCategories(catResult?.categories ?? []);
    } catch (e) {
      Alert.alert('Error', String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const addToCart = async (product: Product) => {
    try {
      await apiService.post('/ecommerceCart/addItem', {
        customerId: 1, sku: product.sku, productId: product.id,
        name: product.name, quantity: 1, unitPrice: product.price,
        merchantId: product.merchantId || 1,
      });
      Alert.alert('Added', `${product.name} added to cart`);
    } catch (e) {
      Alert.alert('Error', String(e));
    }
  };

  const filtered = products.filter(p => {
    if (selectedCategory && p.categoryId !== selectedCategory) return false;
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} placeholder="Search products..." value={search} onChangeText={setSearch} />
      </View>
      {categories.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.catScroll} contentContainerStyle={styles.catContent}>
          <TouchableOpacity style={[styles.catChip, !selectedCategory && styles.catChipActive]} onPress={() => setSelectedCategory(null)}>
            <Text style={[styles.catChipText, !selectedCategory && styles.catChipTextActive]}>All</Text>
          </TouchableOpacity>
          {categories.map(cat => (
            <TouchableOpacity key={cat.id} style={[styles.catChip, selectedCategory === cat.id && styles.catChipActive]} onPress={() => setSelectedCategory(cat.id)}>
              <Text style={[styles.catChipText, selectedCategory === cat.id && styles.catChipTextActive]}>{cat.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
      <FlatList
        data={filtered}
        numColumns={2}
        keyExtractor={(item) => item.sku}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={loadData} />}
        contentContainerStyle={styles.grid}
        renderItem={({ item }) => (
          <View style={styles.productCard}>
            <View style={styles.productImage}>
              {item.imageUrl ? <Image source={{ uri: item.imageUrl }} style={styles.image} /> : <Text style={styles.imagePlaceholder}>📦</Text>}
            </View>
            <Text style={styles.productName} numberOfLines={2}>{item.name}</Text>
            <Text style={styles.productPrice}>NGN {item.price}</Text>
            <TouchableOpacity style={styles.addBtn} onPress={() => addToCart(item)}>
              <Text style={styles.addBtnText}>Add to Cart</Text>
            </TouchableOpacity>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No products found</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  loader: { flex: 1, justifyContent: 'center' },
  searchRow: { padding: 12 },
  searchInput: { borderWidth: 1, borderColor: '#ddd', borderRadius: 12, paddingHorizontal: 16, height: 42 },
  catScroll: { maxHeight: 44 },
  catContent: { paddingHorizontal: 12, gap: 8 },
  catChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#f0f0f0', marginRight: 8 },
  catChipActive: { backgroundColor: '#007AFF' },
  catChipText: { fontSize: 13 },
  catChipTextActive: { color: '#fff', fontWeight: '600' },
  grid: { padding: 8 },
  productCard: { flex: 1, margin: 4, backgroundColor: '#fff', borderRadius: 8, borderWidth: 1, borderColor: '#eee', padding: 8 },
  productImage: { height: 100, backgroundColor: '#f5f5f5', borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  image: { width: '100%', height: '100%', borderRadius: 8 },
  imagePlaceholder: { fontSize: 32 },
  productName: { fontSize: 13, fontWeight: '600', marginBottom: 4 },
  productPrice: { color: '#007AFF', fontWeight: 'bold', marginBottom: 8 },
  addBtn: { backgroundColor: '#007AFF', paddingVertical: 6, borderRadius: 6, alignItems: 'center' },
  addBtnText: { color: '#fff', fontSize: 12, fontWeight: '600' },
  emptyText: { textAlign: 'center', marginTop: 40, color: '#999' },
});
