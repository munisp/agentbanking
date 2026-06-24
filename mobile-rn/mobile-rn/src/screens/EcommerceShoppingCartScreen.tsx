import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert, TextInput, ActivityIndicator, RefreshControl } from 'react-native';
import { apiService } from '../services/apiService';

interface CartItem {
  sku: string;
  productId: number;
  name: string;
  quantity: number;
  unitPrice: string;
  imageUrl?: string;
  merchantId: number;
}

export default function EcommerceShoppingCartScreen({ navigation }: { navigation: any }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [subTotal, setSubTotal] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [currency, setCurrency] = useState('NGN');
  const [couponInput, setCouponInput] = useState('');

  const loadCart = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiService.get('/ecommerceCart/getCart', { customerId: 1 });
      setItems(result?.items ?? []);
      setSubTotal(result?.subTotal ?? 0);
      setDiscount(result?.discountAmount ?? 0);
      setCurrency(result?.currency ?? 'NGN');
    } catch (e) {
      Alert.alert('Error', String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCart(); }, [loadCart]);

  const updateQuantity = async (sku: string, quantity: number) => {
    try {
      await apiService.post('/ecommerceCart/updateItem', { customerId: 1, sku, quantity });
      loadCart();
    } catch (e) {
      Alert.alert('Error', String(e));
    }
  };

  const removeItem = async (sku: string) => {
    try {
      await apiService.post('/ecommerceCart/removeItem', { customerId: 1, sku });
      loadCart();
    } catch (e) {
      Alert.alert('Error', String(e));
    }
  };

  const clearCart = async () => {
    Alert.alert('Clear Cart', 'Remove all items?', [
      { text: 'Cancel' },
      { text: 'Clear', style: 'destructive', onPress: async () => {
        await apiService.post('/ecommerceCart/clearCart', { customerId: 1 });
        loadCart();
      }},
    ]);
  };

  const applyCoupon = async () => {
    if (!couponInput) return;
    try {
      await apiService.post('/ecommerceCart/applyCoupon', { customerId: 1, couponCode: couponInput });
      loadCart();
      Alert.alert('Success', 'Coupon applied!');
    } catch (e) {
      Alert.alert('Invalid Coupon', String(e));
    }
  };

  const total = subTotal - discount;

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  return (
    <View style={styles.container}>
      {items.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>🛒</Text>
          <Text style={styles.emptyText}>Your cart is empty</Text>
          <TouchableOpacity style={styles.browseBtn} onPress={() => navigation.navigate('EcommerceProductCatalog')}>
            <Text style={styles.browseBtnText}>Browse Products</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          <FlatList
            data={items}
            keyExtractor={(item) => item.sku}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={loadCart} />}
            renderItem={({ item }) => {
              const price = parseFloat(item.unitPrice || '0');
              return (
                <View style={styles.cartItem}>
                  <View style={styles.itemInfo}>
                    <Text style={styles.itemName}>{item.name}</Text>
                    <Text style={styles.itemSku}>SKU: {item.sku}</Text>
                    <Text style={styles.itemPrice}>{currency} {price.toFixed(2)}</Text>
                  </View>
                  <View style={styles.qtyControls}>
                    <TouchableOpacity onPress={() => item.quantity > 1 && updateQuantity(item.sku, item.quantity - 1)} style={styles.qtyBtn}>
                      <Text style={styles.qtyBtnText}>-</Text>
                    </TouchableOpacity>
                    <Text style={styles.qtyText}>{item.quantity}</Text>
                    <TouchableOpacity onPress={() => updateQuantity(item.sku, item.quantity + 1)} style={styles.qtyBtn}>
                      <Text style={styles.qtyBtnText}>+</Text>
                    </TouchableOpacity>
                  </View>
                  <TouchableOpacity onPress={() => removeItem(item.sku)}>
                    <Text style={styles.removeBtn}>✕</Text>
                  </TouchableOpacity>
                </View>
              );
            }}
          />
          <View style={styles.couponRow}>
            <TextInput
              style={styles.couponInput}
              placeholder="Coupon code"
              value={couponInput}
              onChangeText={setCouponInput}
            />
            <TouchableOpacity style={styles.applyBtn} onPress={applyCoupon}>
              <Text style={styles.applyBtnText}>Apply</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.summary}>
            <View style={styles.summaryRow}><Text>Subtotal</Text><Text>{currency} {subTotal.toFixed(2)}</Text></View>
            {discount > 0 && <View style={styles.summaryRow}><Text>Discount</Text><Text style={styles.discountText}>-{currency} {discount.toFixed(2)}</Text></View>}
            <View style={[styles.summaryRow, styles.totalRow]}><Text style={styles.totalLabel}>Total</Text><Text style={styles.totalValue}>{currency} {total.toFixed(2)}</Text></View>
            <TouchableOpacity style={styles.checkoutBtn} onPress={() => navigation.navigate('EcommerceCheckout')}>
              <Text style={styles.checkoutBtnText}>Proceed to Checkout ({currency} {total.toFixed(2)})</Text>
            </TouchableOpacity>
          </View>
          {items.length > 0 && (
            <TouchableOpacity style={styles.clearBtn} onPress={clearCart}>
              <Text style={styles.clearBtnText}>Clear Cart</Text>
            </TouchableOpacity>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  loader: { flex: 1, justifyContent: 'center' },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyIcon: { fontSize: 64, marginBottom: 16 },
  emptyText: { fontSize: 18, color: '#999', marginBottom: 16 },
  browseBtn: { backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  browseBtnText: { color: '#fff', fontWeight: '600' },
  cartItem: { flexDirection: 'row', padding: 12, borderBottomWidth: 1, borderBottomColor: '#eee', alignItems: 'center' },
  itemInfo: { flex: 1 },
  itemName: { fontWeight: '600', fontSize: 15 },
  itemSku: { fontSize: 12, color: '#999' },
  itemPrice: { color: '#007AFF', fontWeight: '600', marginTop: 2 },
  qtyControls: { flexDirection: 'row', alignItems: 'center', marginRight: 8 },
  qtyBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#f0f0f0', justifyContent: 'center', alignItems: 'center' },
  qtyBtnText: { fontSize: 18, fontWeight: 'bold' },
  qtyText: { marginHorizontal: 12, fontWeight: '600', fontSize: 16 },
  removeBtn: { color: '#FF3B30', fontSize: 18, fontWeight: 'bold', padding: 4 },
  couponRow: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: '#eee' },
  couponInput: { flex: 1, borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 12, height: 40 },
  applyBtn: { backgroundColor: '#007AFF', paddingHorizontal: 16, justifyContent: 'center', borderRadius: 8, marginLeft: 8 },
  applyBtnText: { color: '#fff', fontWeight: '600' },
  summary: { padding: 16, backgroundColor: '#f9f9f9', borderTopWidth: 1, borderTopColor: '#eee' },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  totalRow: { borderTopWidth: 1, borderTopColor: '#ddd', paddingTop: 8, marginTop: 4 },
  totalLabel: { fontWeight: 'bold', fontSize: 16 },
  totalValue: { fontWeight: 'bold', fontSize: 16 },
  discountText: { color: '#34C759' },
  checkoutBtn: { backgroundColor: '#007AFF', padding: 14, borderRadius: 8, marginTop: 12, alignItems: 'center' },
  checkoutBtnText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  clearBtn: { padding: 12, alignItems: 'center' },
  clearBtnText: { color: '#FF3B30' },
});
