import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput, Alert, Modal,
} from 'react-native';

const API_BASE = 'http://localhost:3001/api/trpc';

interface QRCode {
  code: string;
  amount?: number;
  status: string;
  expiresAt?: string;
  transactionId?: number;
}

interface PaymentResult {
  reference: string;
  status: string;
  amount: number;
  fee: number;
  netAmount: number;
  commission: number;
}

const DynamicQrPaymentScreen: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [generatedQR, setGeneratedQR] = useState<QRCode | null>(null);
  const [recentPayments, setRecentPayments] = useState<PaymentResult[]>([]);
  const [error, setError] = useState('');

  // Generate QR form
  const [genAmount, setGenAmount] = useState('');
  const [genDescription, setGenDescription] = useState('');
  const [generating, setGenerating] = useState(false);

  // Pay QR form
  const [showPay, setShowPay] = useState(false);
  const [payCode, setPayCode] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payPhone, setPayPhone] = useState('');
  const [paying, setPaying] = useState(false);

  const loadRecentPayments = useCallback(async () => {
    try {
      setError('');
      const res = await fetch(`${API_BASE}/dynamicQrPayment.list?input=${encodeURIComponent(JSON.stringify({ limit: 10, offset: 0 }))}`);
      const data = await res.json();
      setRecentPayments(data?.result?.data?.items ?? []);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadRecentPayments(); }, [loadRecentPayments]);

  const generateQR = async () => {
    const amount = genAmount ? parseFloat(genAmount) : undefined;
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/dynamicQrPayment.generateQr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount,
          description: genDescription || undefined,
          currency: 'NGN',
          expiresInMinutes: 30,
        }),
      });
      const data = await res.json();
      const result = data?.result?.data;
      if (result) {
        setGeneratedQR({
          code: result.qrCode,
          amount: result.amount,
          status: 'active',
          expiresAt: result.expiresAt,
          transactionId: result.transactionId,
        });
        Alert.alert('QR Generated', `Code: ${result.qrCode}\n${amount ? `Amount: ₦${amount}` : 'Open amount'}\nExpires: 30 min`);
      }
    } catch (e: any) {
      Alert.alert('Error', e?.message ?? 'Failed to generate QR');
    } finally {
      setGenerating(false);
    }
  };

  const payQR = async () => {
    if (!payCode) { Alert.alert('Error', 'Enter QR code'); return; }
    const amount = parseFloat(payAmount);
    if (!amount || amount <= 0) { Alert.alert('Error', 'Enter valid amount'); return; }
    setPaying(true);
    try {
      const res = await fetch(`${API_BASE}/dynamicQrPayment.payQr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          qrCode: payCode,
          amount,
          customerPhone: payPhone || '08000000000',
          pin: '1234',
        }),
      });
      const data = await res.json();
      const result = data?.result?.data;
      setShowPay(false);
      setPayCode('');
      setPayAmount('');
      setPayPhone('');
      if (result?.reference) {
        Alert.alert('Payment Successful', `Ref: ${result.reference}\nAmount: ₦${amount}\nFee: ₦${result.fee}`);
        loadRecentPayments();
      }
    } catch (e: any) {
      Alert.alert('Payment Failed', e?.message ?? 'Unknown error');
    } finally {
      setPaying(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadRecentPayments(); }} />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Dynamic QR Payments</Text>
        <Text style={styles.subtitle}>Generate and pay via QR codes</Text>
      </View>

      {/* Generate QR Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Generate QR Code</Text>
        <TextInput
          style={styles.input}
          placeholder="Amount (₦) — leave empty for open amount"
          keyboardType="numeric"
          value={genAmount}
          onChangeText={setGenAmount}
        />
        <TextInput
          style={styles.input}
          placeholder="Description (optional)"
          value={genDescription}
          onChangeText={setGenDescription}
        />
        <TouchableOpacity style={styles.primaryBtn} onPress={generateQR} disabled={generating}>
          {generating ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Generate QR Code</Text>}
        </TouchableOpacity>
      </View>

      {/* Generated QR Display */}
      {generatedQR && (
        <View style={styles.qrCard}>
          <Text style={styles.qrTitle}>Generated QR</Text>
          <View style={styles.qrBox}>
            <Text style={styles.qrCode}>{generatedQR.code}</Text>
          </View>
          <Text style={styles.qrDetail}>Amount: {generatedQR.amount ? `₦${generatedQR.amount}` : 'Open'}</Text>
          <Text style={styles.qrDetail}>Status: {generatedQR.status}</Text>
          {generatedQR.expiresAt && (
            <Text style={styles.qrExpiry}>Expires: {new Date(generatedQR.expiresAt).toLocaleString()}</Text>
          )}
        </View>
      )}

      {/* Pay QR Button */}
      <TouchableOpacity style={styles.payBtn} onPress={() => setShowPay(true)}>
        <Text style={styles.payBtnText}>📱 Scan & Pay QR Code</Text>
      </TouchableOpacity>

      {/* Recent Transactions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Transactions</Text>
        {recentPayments.length === 0 ? (
          <Text style={styles.emptyText}>No transactions yet</Text>
        ) : (
          recentPayments.map((p: any, i: number) => (
            <View key={p.reference || i} style={styles.txCard}>
              <View>
                <Text style={styles.txRef}>{p.reference || `Transaction ${i + 1}`}</Text>
                <Text style={styles.txAmount}>₦{p.amount ?? 0}</Text>
              </View>
              <View style={[styles.statusBadge, { backgroundColor: p.status === 'completed' ? '#dcfce7' : '#fef3c7' }]}>
                <Text style={[styles.statusText, { color: p.status === 'completed' ? '#16a34a' : '#d97706' }]}>
                  {p.status || 'pending'}
                </Text>
              </View>
            </View>
          ))
        )}
      </View>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {/* Pay QR Modal */}
      <Modal visible={showPay} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Pay via QR Code</Text>
            <TextInput style={styles.input} placeholder="QR Code" value={payCode} onChangeText={setPayCode} />
            <TextInput style={styles.input} placeholder="Amount (₦)" keyboardType="numeric" value={payAmount} onChangeText={setPayAmount} />
            <TextInput style={styles.input} placeholder="Phone number" keyboardType="phone-pad" value={payPhone} onChangeText={setPayPhone} />
            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowPay(false)}>
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.primaryBtn2} onPress={payQR} disabled={paying}>
                {paying ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Pay Now</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: { padding: 20, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: '#111827' },
  subtitle: { fontSize: 14, color: '#6b7280', marginTop: 4 },
  section: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#111827', marginBottom: 12 },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, padding: 14, marginBottom: 12, fontSize: 16, backgroundColor: '#fff' },
  primaryBtn: { backgroundColor: '#0D7377', padding: 16, borderRadius: 12, alignItems: 'center' },
  primaryBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  qrCard: { backgroundColor: '#fff', margin: 16, padding: 20, borderRadius: 16, alignItems: 'center', elevation: 2 },
  qrTitle: { fontSize: 18, fontWeight: '600', marginBottom: 12 },
  qrBox: { backgroundColor: '#f3f4f6', padding: 20, borderRadius: 12, marginBottom: 12 },
  qrCode: { fontSize: 16, fontWeight: '600', fontFamily: 'monospace', color: '#0D7377' },
  qrDetail: { fontSize: 14, color: '#374151', marginTop: 4 },
  qrExpiry: { fontSize: 12, color: '#9ca3af', marginTop: 4 },
  payBtn: { backgroundColor: '#2563eb', margin: 16, padding: 16, borderRadius: 12, alignItems: 'center' },
  payBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  txCard: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fff', padding: 14, borderRadius: 10, marginBottom: 8 },
  txRef: { fontSize: 14, fontWeight: '600', color: '#111827' },
  txAmount: { fontSize: 16, fontWeight: '700', color: '#0D7377', marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  statusText: { fontSize: 12, fontWeight: '600' },
  emptyText: { color: '#9ca3af', fontSize: 14, textAlign: 'center', padding: 20 },
  errorText: { color: '#ef4444', textAlign: 'center', padding: 16 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24 },
  modalTitle: { fontSize: 20, fontWeight: '700', marginBottom: 16, textAlign: 'center' },
  modalActions: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  cancelBtn: { flex: 1, padding: 14, marginRight: 8, borderRadius: 8, borderWidth: 1, borderColor: '#d1d5db', alignItems: 'center' },
  cancelText: { color: '#6b7280', fontWeight: '600' },
  primaryBtn2: { flex: 2, padding: 14, borderRadius: 8, backgroundColor: '#0D7377', alignItems: 'center' },
});

export default DynamicQrPaymentScreen;
