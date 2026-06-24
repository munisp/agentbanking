import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert, TextInput, ActivityIndicator, ScrollView } from 'react-native';
import { apiService } from '../services/apiService';

export default function EcommerceCheckoutScreen({ navigation }: { navigation: any }) {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<any[]>([]);
  const [subTotal, setSubTotal] = useState(0);
  const [currency, setCurrency] = useState('NGN');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [orderId, setOrderId] = useState('');
  const shippingFee = 500;
  const tax = subTotal * 0.075;
  const total = subTotal + shippingFee + tax;

  useEffect(() => {
    (async () => {
      try {
        const result = await apiService.get('/ecommerceCart/getCart', { customerId: 1 });
        setItems(result?.items ?? []);
        setSubTotal(result?.subTotal ?? 0);
        setCurrency(result?.currency ?? 'NGN');
      } catch (e) {
        Alert.alert('Error', String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const placeOrder = async () => {
    if (!name || !address) { Alert.alert('Required', 'Please fill name and address'); return; }
    setLoading(true);
    try {
      const result = await apiService.post('/ecommerceOrders/createOrder', {
        customerId: 1,
        items: items.map(i => ({ sku: i.sku, productId: i.productId, quantity: i.quantity, unitPrice: i.unitPrice, merchantId: i.merchantId || 1 })),
        shippingAddress: address, phone, paymentMethod, currency,
      });
      setOrderId(result?.orderId?.toString() ?? '');
      setStep(2);
    } catch (e) {
      Alert.alert('Error', String(e));
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <ActivityIndicator style={styles.loader} size="large" />;

  const paymentMethods = [
    { key: 'card', label: 'Card (Paystack/Flutterwave)' },
    { key: 'bank_transfer', label: 'Bank Transfer' },
    { key: 'ussd', label: 'USSD' },
    { key: 'cod', label: 'Cash on Delivery' },
  ];

  return (
    <ScrollView style={styles.container}>
      {/* Step indicators */}
      <View style={styles.steps}>
        {['Shipping', 'Payment', 'Done'].map((s, i) => (
          <View key={s} style={[styles.stepDot, i <= step && styles.stepDotActive]}>
            <Text style={[styles.stepText, i <= step && styles.stepTextActive]}>{s}</Text>
          </View>
        ))}
      </View>

      {step === 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Shipping Details</Text>
          <TextInput style={styles.input} placeholder="Full Name" value={name} onChangeText={setName} />
          <TextInput style={styles.input} placeholder="Phone Number" value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
          <TextInput style={styles.input} placeholder="Delivery Address" value={address} onChangeText={setAddress} multiline />
          <TouchableOpacity style={styles.nextBtn} onPress={() => name && address ? setStep(1) : Alert.alert('Required', 'Fill name and address')}>
            <Text style={styles.nextBtnText}>Continue to Payment</Text>
          </TouchableOpacity>
        </View>
      )}

      {step === 1 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Payment Method</Text>
          {paymentMethods.map(pm => (
            <TouchableOpacity key={pm.key} style={[styles.paymentOption, paymentMethod === pm.key && styles.paymentOptionActive]} onPress={() => setPaymentMethod(pm.key)}>
              <View style={[styles.radio, paymentMethod === pm.key && styles.radioActive]} />
              <Text style={styles.paymentLabel}>{pm.label}</Text>
            </TouchableOpacity>
          ))}
          <View style={styles.summarySection}>
            <View style={styles.row}><Text>Subtotal</Text><Text>{currency} {subTotal.toFixed(2)}</Text></View>
            <View style={styles.row}><Text>Shipping</Text><Text>{currency} {shippingFee.toFixed(2)}</Text></View>
            <View style={styles.row}><Text>VAT (7.5%)</Text><Text>{currency} {tax.toFixed(2)}</Text></View>
            <View style={[styles.row, styles.totalRow]}><Text style={styles.totalLabel}>Total</Text><Text style={styles.totalValue}>{currency} {total.toFixed(2)}</Text></View>
          </View>
          <View style={styles.btnRow}>
            <TouchableOpacity style={styles.backBtn} onPress={() => setStep(0)}><Text>Back</Text></TouchableOpacity>
            <TouchableOpacity style={styles.nextBtn} onPress={placeOrder}><Text style={styles.nextBtnText}>Place Order</Text></TouchableOpacity>
          </View>
        </View>
      )}

      {step === 2 && (
        <View style={styles.confirmation}>
          <Text style={styles.checkIcon}>✓</Text>
          <Text style={styles.confirmTitle}>Order Placed!</Text>
          {orderId ? <Text style={styles.orderId}>Order #{orderId}</Text> : null}
          <TouchableOpacity style={styles.nextBtn} onPress={() => navigation.navigate('EcommerceOrderManagement')}>
            <Text style={styles.nextBtnText}>View My Orders</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  loader: { flex: 1, justifyContent: 'center' },
  steps: { flexDirection: 'row', justifyContent: 'center', paddingVertical: 16, gap: 24 },
  stepDot: { alignItems: 'center' },
  stepDotActive: {},
  stepText: { color: '#999', fontSize: 13 },
  stepTextActive: { color: '#007AFF', fontWeight: '600' },
  section: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: 'bold', marginBottom: 16 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginBottom: 12, fontSize: 15 },
  paymentOption: { flexDirection: 'row', alignItems: 'center', padding: 14, borderWidth: 1, borderColor: '#eee', borderRadius: 8, marginBottom: 8 },
  paymentOptionActive: { borderColor: '#007AFF', backgroundColor: '#F0F7FF' },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#ccc', marginRight: 12 },
  radioActive: { borderColor: '#007AFF', backgroundColor: '#007AFF' },
  paymentLabel: { fontSize: 15 },
  summarySection: { marginTop: 16, padding: 12, backgroundColor: '#f9f9f9', borderRadius: 8 },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  totalRow: { borderTopWidth: 1, borderTopColor: '#ddd', paddingTop: 8, marginTop: 4 },
  totalLabel: { fontWeight: 'bold', fontSize: 16 },
  totalValue: { fontWeight: 'bold', fontSize: 16 },
  btnRow: { flexDirection: 'row', gap: 12, marginTop: 16 },
  backBtn: { flex: 1, padding: 14, borderRadius: 8, borderWidth: 1, borderColor: '#ddd', alignItems: 'center' },
  nextBtn: { flex: 1, backgroundColor: '#007AFF', padding: 14, borderRadius: 8, alignItems: 'center', marginTop: 16 },
  nextBtnText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  confirmation: { alignItems: 'center', paddingTop: 60 },
  checkIcon: { fontSize: 64, color: '#34C759', marginBottom: 16 },
  confirmTitle: { fontSize: 22, fontWeight: 'bold', marginBottom: 8 },
  orderId: { color: '#999', marginBottom: 24 },
});
