import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

export default function TransactionMonitorScreen() {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 600));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Transaction Monitor</Text>
      </View>
      {loading ? (
        <ActivityIndicator style={styles.loader} color="#3b82f6" />
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardIcon}>⬡</Text>
              <View style={styles.cardHeaderText}>
                <Text style={styles.cardTitle}>Transaction Monitor</Text>
                <Text style={styles.cardSubtitle}>
                  Manage your transaction monitor settings and data
                </Text>
              </View>
            </View>
          </View>
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Overview</Text>
            <Text style={styles.sectionBody}>
              This screen provides transaction monitor functionality. Data is loaded from the
              54Link API backend.
            </Text>
          </View>
          <TouchableOpacity style={styles.refreshBtn} onPress={load}>
            <Text style={styles.refreshBtnText}>↻  Refresh</Text>
          </TouchableOpacity>
        </ScrollView>
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
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, elevation: 2, marginBottom: 16 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  cardIcon: { fontSize: 32, color: '#3b82f6' },
  cardHeaderText: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#111827', marginBottom: 4 },
  cardSubtitle: { fontSize: 13, color: '#6b7280' },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#111827', marginBottom: 8 },
  sectionBody: { fontSize: 14, color: '#4b5563', lineHeight: 22 },
  refreshBtn: { backgroundColor: '#3b82f6', borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  refreshBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
