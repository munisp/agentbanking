import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface FirmwareVersion {
  id: string;
  version: string;
  status: string;
  checksum: string;
  releaseNotes?: string;
  publishedAt: string;
  forceUpdate: boolean;
  minAppVersion?: string;
}

interface RolloutStage {
  percentage: number;
  status: string;
  failureRate: number;
}

const POSFirmwareOTAScreen: React.FC = () => {
  const [versions, setVersions] = useState<FirmwareVersion[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const currentVersion = '4.2.1';
  const rolloutStages: RolloutStage[] = [
    { percentage: 5, status: 'completed', failureRate: 0.2 },
    { percentage: 25, status: 'completed', failureRate: 0.8 },
    { percentage: 50, status: 'in_progress', failureRate: 1.5 },
    { percentage: 100, status: 'pending', failureRate: 0 },
  ];

  const load = useCallback(async () => {
    try {
      setError('');
      const [listResp, statsResp] = await Promise.all([
        apiClient.get('/api/trpc/posFirmwareOTA.listVersions?input={"json":{"limit":20}}'),
        apiClient.get('/api/trpc/posFirmwareOTA.getStats'),
      ]);
      setVersions(listResp.data?.result?.data?.json?.items ?? []);
      setStats(statsResp.data?.result?.data?.json ?? {});
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const startRollout = (versionId: string) => {
    Alert.alert('Start Rollout?', 'Begin staged canary rollout (5% → 25% → 50% → 100%)?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Start',
        onPress: async () => {
          try {
            await apiClient.post('/api/trpc/posFirmwareOTA.startRollout', {
              json: { versionId },
            });
            Alert.alert('Success', 'Rollout started at 5%');
            load();
          } catch (e: any) {
            Alert.alert('Error', e?.message ?? 'Failed');
          }
        },
      },
    ]);
  };

  const rollback = () => {
    Alert.alert('Rollback?', 'Rollback firmware to previous stable version?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Rollback',
        style: 'destructive',
        onPress: async () => {
          try {
            await apiClient.post('/api/trpc/posFirmwareOTA.rollbackRollout', {
              json: { reason: 'Manual rollback from mobile app' },
            });
            Alert.alert('Success', 'Firmware rollback initiated');
            load();
          } catch (e: any) {
            Alert.alert('Error', e?.message ?? 'Failed');
          }
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>Loading firmware...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={load}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Firmware Updates</Text>

      {/* Current version */}
      <View style={styles.currentCard}>
        <Text style={styles.currentLabel}>Current Firmware</Text>
        <Text style={styles.currentVersion}>v{currentVersion}</Text>
      </View>

      {/* Canary rollout progress */}
      <View style={styles.rolloutCard}>
        <Text style={styles.sectionTitle}>Canary Rollout Progress</Text>
        <Text style={styles.subtitle}>Max failure rate: 5%</Text>
        {rolloutStages.map((stage) => (
          <View key={stage.percentage} style={styles.stageRow}>
            <Text style={[styles.stageIcon, {
              color: stage.status === 'completed' ? '#16a34a' :
                     stage.status === 'in_progress' ? '#3b82f6' : '#d1d5db',
            }]}>
              {stage.status === 'completed' ? '\u2713' : stage.status === 'in_progress' ? '\u25CF' : '\u25CB'}
            </Text>
            <Text style={styles.stagePercent}>{stage.percentage}%</Text>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, {
                width: `${stage.status === 'completed' ? 100 : stage.status === 'in_progress' ? 60 : 0}%` as any,
                backgroundColor: stage.status === 'completed' ? '#16a34a' : '#3b82f6',
              }]} />
            </View>
            <Text style={[styles.failRate, stage.failureRate > 5 && { color: '#dc2626' }]}>
              Fail: {stage.failureRate}%
            </Text>
          </View>
        ))}
        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.advanceBtn}>
            <Text style={styles.advanceBtnText}>Advance Stage</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.rollbackBtn} onPress={rollback}>
            <Text style={styles.rollbackBtnText}>Rollback</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Version list */}
      <Text style={[styles.sectionTitle, { paddingHorizontal: 16, marginTop: 12 }]}>Update History</Text>
      <FlatList
        data={versions}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <View style={styles.versionCard}>
            <View style={styles.versionHeader}>
              <View>
                <Text style={styles.versionName}>v{item.version}</Text>
                <Text style={styles.versionDate}>{item.publishedAt}</Text>
                <Text style={styles.checksum}>SHA: {item.checksum.substring(0, 12)}...</Text>
              </View>
              <View style={[styles.badge, { backgroundColor: '#f0fdf4' }]}>
                <Text style={[styles.badgeText, { color: '#16a34a' }]}>
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>
            {item.forceUpdate && (
              <View style={styles.forceTag}>
                <Text style={styles.forceTagText}>FORCE UPDATE</Text>
              </View>
            )}
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.center}><Text>No versions found</Text></View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  header: { fontSize: 22, fontWeight: '700', padding: 16, color: '#1e293b' },
  loadingText: { marginTop: 8, color: '#64748b' },
  errorText: { color: '#dc2626', fontSize: 16, textAlign: 'center', marginBottom: 12 },
  retryBtn: { backgroundColor: '#2563eb', paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '600' },
  currentCard: { backgroundColor: '#fff', marginHorizontal: 16, padding: 16, borderRadius: 12, marginBottom: 12 },
  currentLabel: { fontSize: 13, color: '#64748b' },
  currentVersion: { fontSize: 28, fontWeight: '800', color: '#1e293b', marginTop: 4 },
  rolloutCard: { backgroundColor: '#fff', marginHorizontal: 16, padding: 16, borderRadius: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#1e293b', marginBottom: 4 },
  subtitle: { fontSize: 12, color: '#94a3b8', marginBottom: 12 },
  stageRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  stageIcon: { fontSize: 16, width: 20, textAlign: 'center' },
  stagePercent: { width: 36, fontSize: 13, fontWeight: '600' },
  progressBarBg: { flex: 1, height: 6, borderRadius: 3, backgroundColor: '#e5e7eb' },
  progressBarFill: { height: 6, borderRadius: 3 },
  failRate: { fontSize: 11, color: '#94a3b8', width: 60 },
  actionRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  advanceBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, backgroundColor: '#16a34a', alignItems: 'center' },
  advanceBtnText: { color: '#fff', fontWeight: '600', fontSize: 13 },
  rollbackBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#dc2626', alignItems: 'center' },
  rollbackBtnText: { color: '#dc2626', fontWeight: '600', fontSize: 13 },
  versionCard: { backgroundColor: '#fff', marginHorizontal: 16, marginVertical: 4, padding: 14, borderRadius: 12 },
  versionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  versionName: { fontSize: 16, fontWeight: '700', color: '#1e293b' },
  versionDate: { fontSize: 12, color: '#94a3b8', marginTop: 2 },
  checksum: { fontSize: 11, color: '#94a3b8', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  forceTag: { marginTop: 6, backgroundColor: '#fef2f2', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start' },
  forceTagText: { fontSize: 11, fontWeight: '700', color: '#dc2626' },
});

export default POSFirmwareOTAScreen;
