import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

type Journey = {
  id: string;
  title: string;
  description: string;
  steps: number;
  completed: number;
  status: 'active' | 'completed';
};

const MOCK_JOURNEYS: Journey[] = [
  {
    id: '1',
    title: 'Onboarding Journey',
    description: 'Complete your agent profile and first transaction',
    steps: 5,
    completed: 3,
    status: 'active',
  },
  {
    id: '2',
    title: 'Gold Agent Path',
    description: 'Reach Gold tier with 500 transactions',
    steps: 10,
    completed: 7,
    status: 'active',
  },
  {
    id: '3',
    title: 'Compliance Certification',
    description: 'Complete AML/KYC training modules',
    steps: 3,
    completed: 3,
    status: 'completed',
  },
];

export default function JourneysScreen() {
  const navigation = useNavigation();
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (isRefresh = false) => {
    if (!isRefresh) setLoading(true);
    await new Promise(r => setTimeout(r, 400));
    setJourneys(MOCK_JOURNEYS);
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => { load(); }, []);

  const renderItem = ({ item }: { item: Journey }) => {
    const progress = item.completed / item.steps;
    const done = item.status === 'completed';
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={[styles.icon, done ? styles.iconDone : styles.iconActive]}>
            {done ? '✓' : '→'}
          </Text>
          <Text style={styles.cardTitle}>{item.title}</Text>
          {done && <View style={styles.doneBadge}><Text style={styles.doneBadgeText}>Done</Text></View>}
        </View>
        <Text style={styles.cardDesc}>{item.description}</Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progress * 100}%` as any, backgroundColor: done ? '#22c55e' : '#3b82f6' }]} />
        </View>
        <Text style={styles.stepCount}>{item.completed} / {item.steps} steps</Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>My Journeys</Text>
      </View>
      {loading ? (
        <ActivityIndicator style={styles.loader} color="#3b82f6" />
      ) : (
        <FlatList
          data={journeys}
          keyExtractor={i => i.id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); load(true); }}
              colors={['#3b82f6']}
            />
          }
        />
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
  list: { padding: 16, gap: 12 },
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, elevation: 2 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  icon: { fontSize: 18, fontWeight: '700', marginRight: 8 },
  iconActive: { color: '#3b82f6' },
  iconDone: { color: '#22c55e' },
  cardTitle: { flex: 1, fontSize: 15, fontWeight: '600', color: '#111827' },
  doneBadge: { backgroundColor: '#22c55e', borderRadius: 12, paddingHorizontal: 8, paddingVertical: 2 },
  doneBadgeText: { color: '#fff', fontSize: 11, fontWeight: '600' },
  cardDesc: { fontSize: 13, color: '#6b7280', marginBottom: 12 },
  progressTrack: { height: 6, backgroundColor: '#e5e7eb', borderRadius: 3, overflow: 'hidden', marginBottom: 4 },
  progressFill: { height: '100%', borderRadius: 3 },
  stepCount: { fontSize: 12, color: '#9ca3af' },
});
