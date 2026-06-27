import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface KYCStatus {
  tier: number;
  status: string;
  bvnVerified: boolean;
  ninVerified: boolean;
  addressVerified: boolean;
  livenessVerified: boolean;
  documentsSubmitted: number;
  dailyLimit: number;
  singleTxLimit: number;
  nextTierRequirements: string[];
}

const KYCScreen: React.FC = () => {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [kycStatus, setKycStatus] = useState<KYCStatus | null>(null);

  const loadKYC = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const response = await apiClient.get('/kyc/status');
      const data = response as any;
      setKycStatus({
        tier: data.tier ?? data.kycTier ?? 1,
        status: data.status ?? 'pending',
        bvnVerified: data.bvnVerified ?? data.bvn_verified ?? false,
        ninVerified: data.ninVerified ?? data.nin_verified ?? false,
        addressVerified: data.addressVerified ?? data.address_verified ?? false,
        livenessVerified: data.livenessVerified ?? data.liveness_verified ?? false,
        documentsSubmitted: data.documentsSubmitted ?? data.documents_submitted ?? 0,
        dailyLimit: data.dailyLimit ?? data.daily_limit ?? 50000,
        singleTxLimit: data.singleTxLimit ?? data.single_tx_limit ?? 50000,
        nextTierRequirements: data.nextTierRequirements ?? data.requirements ?? [],
      });
    } catch (e) {
      setKycStatus({
        tier: 1, status: 'pending', bvnVerified: false, ninVerified: false,
        addressVerified: false, livenessVerified: false, documentsSubmitted: 0,
        dailyLimit: 50000, singleTxLimit: 50000,
        nextTierRequirements: ['BVN Verification', 'NIN Verification'],
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadKYC(); }, [loadKYC]);

  const startVerification = (type: string) => {
    (navigation as any).navigate('KYCVerification', { verificationType: type });
  };

  if (loading || !kycStatus) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading KYC status...</Text>
      </View>
    );
  }

  const tierColor = kycStatus.tier >= 3 ? '#4CAF50' : kycStatus.tier >= 2 ? '#FF9800' : '#D32F2F';
  const tierProgress = (kycStatus.tier / 3) * 100;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadKYC(true)} />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>KYC Verification</Text>
        <Text style={styles.subtitle}>CBN Tier {kycStatus.tier} of 3</Text>
      </View>

      <View style={styles.tierCard}>
        <View style={styles.tierHeader}>
          <Text style={[styles.tierBadge, { backgroundColor: tierColor }]}>TIER {kycStatus.tier}</Text>
          <Text style={styles.tierStatus}>{kycStatus.status.toUpperCase()}</Text>
        </View>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${tierProgress}%`, backgroundColor: tierColor }]} />
        </View>
        <View style={styles.limitsRow}>
          <View style={styles.limitItem}>
            <Text style={styles.limitLabel}>Daily Limit</Text>
            <Text style={styles.limitValue}>NGN {kycStatus.dailyLimit.toLocaleString()}</Text>
          </View>
          <View style={styles.limitItem}>
            <Text style={styles.limitLabel}>Per Transaction</Text>
            <Text style={styles.limitValue}>NGN {kycStatus.singleTxLimit.toLocaleString()}</Text>
          </View>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Verification Status</Text>
        {[
          { label: 'BVN Verification', done: kycStatus.bvnVerified, type: 'bvn' },
          { label: 'NIN Verification', done: kycStatus.ninVerified, type: 'nin' },
          { label: 'Address Verification', done: kycStatus.addressVerified, type: 'address' },
          { label: 'Liveness Check', done: kycStatus.livenessVerified, type: 'liveness' },
        ].map(item => (
          <View key={item.type} style={styles.verifyRow}>
            <View style={[styles.statusDot, { backgroundColor: item.done ? '#4CAF50' : '#DDD' }]} />
            <Text style={styles.verifyLabel}>{item.label}</Text>
            {!item.done && (
              <TouchableOpacity style={styles.verifyBtn} onPress={() => startVerification(item.type)}>
                <Text style={styles.verifyBtnText}>Verify</Text>
              </TouchableOpacity>
            )}
            {item.done && <Text style={styles.verifiedText}>Verified</Text>}
          </View>
        ))}
      </View>

      {kycStatus.nextTierRequirements.length > 0 && kycStatus.tier < 3 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Upgrade to Tier {kycStatus.tier + 1}</Text>
          {kycStatus.nextTierRequirements.map((req, i) => (
            <Text key={i} style={styles.requirementText}>{i + 1}. {req}</Text>
          ))}
        </View>
      )}
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
  tierCard: { backgroundColor: '#FFF', margin: 16, borderRadius: 12, padding: 20 },
  tierHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  tierBadge: { color: '#FFF', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 4, fontWeight: 'bold', fontSize: 14, overflow: 'hidden' },
  tierStatus: { fontSize: 13, color: '#888', fontWeight: '600' },
  progressBar: { height: 8, backgroundColor: '#F0F0F0', borderRadius: 4, marginBottom: 16 },
  progressFill: { height: 8, borderRadius: 4 },
  limitsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  limitItem: { alignItems: 'center' },
  limitLabel: { fontSize: 12, color: '#888' },
  limitValue: { fontSize: 16, fontWeight: '600', color: '#333', marginTop: 4 },
  section: { backgroundColor: '#FFF', marginHorizontal: 16, marginBottom: 16, borderRadius: 12, padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#333', marginBottom: 16 },
  verifyRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  statusDot: { width: 12, height: 12, borderRadius: 6, marginRight: 12 },
  verifyLabel: { flex: 1, fontSize: 15, color: '#333' },
  verifyBtn: { backgroundColor: '#007AFF', paddingHorizontal: 16, paddingVertical: 6, borderRadius: 6 },
  verifyBtnText: { color: '#FFF', fontSize: 13, fontWeight: '600' },
  verifiedText: { color: '#4CAF50', fontSize: 14, fontWeight: '600' },
  requirementText: { fontSize: 14, color: '#666', marginBottom: 8 },
});

export default KYCScreen;
