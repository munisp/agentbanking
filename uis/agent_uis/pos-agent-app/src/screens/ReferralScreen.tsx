import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  Share,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

export default function ReferralScreen() {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<{ referral_code: string; total_earnings: number; referral_count: number } | null>(null);

  useEffect(() => {
    setTimeout(() => {
      setData({ referral_code: '54LNK-X9A2', total_earnings: 15000, referral_count: 6 });
      setLoading(false);
    }, 500);
  }, []);

  const shareCode = async () => {
    if (!data) return;
    await Share.share({ message: `Join 54Link Agent Banking with my referral code: ${data.referral_code}` });
  };

  const earnings = (data?.total_earnings ?? 0) / 100;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Refer & Earn</Text>
      </View>
      {loading ? (
        <ActivityIndicator style={styles.loader} color="#3b82f6" />
      ) : (
        <View style={styles.content}>
          <View style={styles.codeCard}>
            <Text style={styles.codeLabel}>Your Referral Code</Text>
            <Text style={styles.code}>{data?.referral_code}</Text>
            <TouchableOpacity style={styles.shareBtn} onPress={shareCode}>
              <Text style={styles.shareBtnText}>Share Code</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.statsRow}>
            <View style={styles.statCard}>
              <Text style={styles.statValue}>{data?.referral_count}</Text>
              <Text style={styles.statLabel}>Referrals</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statValue}>₦{earnings.toFixed(2)}</Text>
              <Text style={styles.statLabel}>Earnings</Text>
            </View>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  backBtn: { marginRight: 12 },
  backText: { fontSize: 18, color: '#3b82f6' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#111827' },
  loader: { marginTop: 60 },
  content: { padding: 16, gap: 16 },
  codeCard: { backgroundColor: '#fff', borderRadius: 12, padding: 20, alignItems: 'center', shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, elevation: 2 },
  codeLabel: { fontSize: 13, color: '#6b7280', marginBottom: 8 },
  code: { fontSize: 28, fontWeight: '700', letterSpacing: 4, color: '#111827', marginBottom: 16 },
  shareBtn: { backgroundColor: '#3b82f6', borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 8 },
  shareBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  statsRow: { flexDirection: 'row', gap: 12 },
  statCard: { flex: 1, backgroundColor: '#fff', borderRadius: 12, padding: 16, alignItems: 'center', shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, elevation: 2 },
  statValue: { fontSize: 24, fontWeight: '700', color: '#111827', marginBottom: 4 },
  statLabel: { fontSize: 13, color: '#6b7280' },
});
