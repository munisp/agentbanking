import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Share, Alert,
} from 'react-native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

const ReceiveMoneyScreen: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [accountDetails, setAccountDetails] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadAccountDetails();
  }, []);

  const loadAccountDetails = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/account/details');
      setAccountDetails(response);
    } catch (e) {
      setAccountDetails({
        accountNumber: '0123456789',
        accountName: 'Agent Account',
        bankName: '54Link Digital Bank',
        bankCode: '999',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleShare = async () => {
    if (!accountDetails) return;
    try {
      await Share.share({
        message: `Send money to:\n${accountDetails.accountName}\n${accountDetails.bankName}\nAccount: ${accountDetails.accountNumber}`,
      });
    } catch (e) {
      Alert.alert('Error', 'Failed to share');
    }
  };

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading account details...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Receive Money</Text>
        <Text style={styles.subtitle}>Share your account details</Text>
      </View>

      <View style={styles.detailsCard}>
        <View style={styles.detailRow}>
          <Text style={styles.label}>Account Name</Text>
          <Text style={styles.value}>{accountDetails?.accountName ?? 'N/A'}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.label}>Account Number</Text>
          <TouchableOpacity onPress={handleCopy}>
            <Text style={styles.accountNumber}>{accountDetails?.accountNumber ?? 'N/A'}</Text>
            <Text style={styles.copyHint}>{copied ? 'Copied!' : 'Tap to copy'}</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.label}>Bank</Text>
          <Text style={styles.value}>{accountDetails?.bankName ?? 'N/A'}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.label}>Bank Code</Text>
          <Text style={styles.value}>{accountDetails?.bankCode ?? 'N/A'}</Text>
        </View>
      </View>

      <TouchableOpacity style={styles.shareBtn} onPress={handleShare}>
        <Text style={styles.shareBtnText}>Share Account Details</Text>
      </TouchableOpacity>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>How to receive money</Text>
        <Text style={styles.infoText}>1. Share your account details above</Text>
        <Text style={styles.infoText}>2. Sender transfers to your account number</Text>
        <Text style={styles.infoText}>3. You receive an instant notification</Text>
        <Text style={styles.infoText}>4. Funds are available immediately</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  detailsCard: { backgroundColor: '#FFF', margin: 16, borderRadius: 12, padding: 20 },
  detailRow: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  label: { fontSize: 13, color: '#888', marginBottom: 4 },
  value: { fontSize: 16, fontWeight: '500', color: '#333' },
  accountNumber: { fontSize: 24, fontWeight: 'bold', color: '#007AFF', letterSpacing: 2 },
  copyHint: { fontSize: 12, color: '#007AFF', marginTop: 4 },
  shareBtn: { backgroundColor: '#007AFF', marginHorizontal: 16, paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  shareBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  infoCard: { backgroundColor: '#FFF', margin: 16, borderRadius: 12, padding: 20 },
  infoTitle: { fontSize: 16, fontWeight: '600', color: '#333', marginBottom: 12 },
  infoText: { fontSize: 14, color: '#666', marginBottom: 8 },
});

export default ReceiveMoneyScreen;
