import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface TerminalInfo {
  id: string;
  serialNumber: string;
  model: string;
  status: string;
  batteryLevel: number;
  signalStrength: number;
  firmwareVersion: string;
  lastSeen: string;
  agentCode?: string;
}

interface FleetStats {
  total: number;
  active: number;
  suspended: number;
  offline: number;
}

const POSShellScreen: React.FC = () => {
  const [terminals, setTerminals] = useState<TerminalInfo[]>([]);
  const [stats, setStats] = useState<FleetStats>({ total: 0, active: 0, suspended: 0, offline: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const [listResp, statsResp] = await Promise.all([
        apiClient.get('/api/trpc/posTerminalFleet.list?input={"json":{"limit":50}}'),
        apiClient.get('/api/trpc/posTerminalFleet.getStats'),
      ]);
      setTerminals(listResp.data?.result?.data?.json?.items ?? []);
      const s = statsResp.data?.result?.data?.json;
      if (s) setStats(s);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sendCommand = (terminal: TerminalInfo, command: string) => {
    Alert.alert(
      `Send ${command}?`,
      `Send "${command}" to ${terminal.serialNumber}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Send',
          onPress: async () => {
            try {
              await apiClient.post('/api/trpc/posTerminalFleet.sendCommand', {
                json: { terminalId: terminal.id, command },
              });
              Alert.alert('Success', `Command "${command}" sent to ${terminal.serialNumber}`);
            } catch (e: any) {
              Alert.alert('Error', e?.message ?? 'Failed to send command');
            }
          },
        },
      ],
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#16a34a';
      case 'suspended': return '#f59e0b';
      case 'terminated': return '#dc2626';
      default: return '#6b7280';
    }
  };

  const getBatteryColor = (level: number) => {
    if (level > 50) return '#16a34a';
    if (level > 20) return '#f59e0b';
    return '#dc2626';
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>Loading fleet...</Text>
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
      <Text style={styles.header}>Terminal Fleet</Text>

      {/* Stats */}
      <View style={styles.statsRow}>
        <View style={[styles.statCard, { backgroundColor: '#f0fdf4' }]}>
          <Text style={[styles.statValue, { color: '#16a34a' }]}>{stats.active}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: '#fffbeb' }]}>
          <Text style={[styles.statValue, { color: '#f59e0b' }]}>{stats.suspended}</Text>
          <Text style={styles.statLabel}>Suspended</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: '#eff6ff' }]}>
          <Text style={[styles.statValue, { color: '#2563eb' }]}>{stats.total}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
      </View>

      {/* Terminal list */}
      <FlatList
        data={terminals}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View>
                <Text style={styles.serialNumber}>{item.serialNumber}</Text>
                <Text style={styles.model}>{item.model}</Text>
              </View>
              <View style={[styles.badge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
                <Text style={[styles.badgeText, { color: getStatusColor(item.status) }]}>
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>

            <View style={styles.metricsRow}>
              <Text style={[styles.metric, { color: getBatteryColor(item.batteryLevel) }]}>
                {item.batteryLevel}%
              </Text>
              <Text style={styles.metric}>{item.signalStrength}dBm</Text>
              <Text style={styles.metric}>v{item.firmwareVersion}</Text>
              <Text style={styles.metricLight}>{item.lastSeen}</Text>
            </View>

            <View style={styles.commandRow}>
              {['reboot', 'lock', 'diagnostics'].map((cmd) => (
                <TouchableOpacity
                  key={cmd}
                  style={[styles.cmdBtn, cmd === 'lock' && styles.cmdBtnDanger]}
                  onPress={() => sendCommand(item, cmd)}
                >
                  <Text style={[styles.cmdText, cmd === 'lock' && styles.cmdTextDanger]}>
                    {cmd.charAt(0).toUpperCase() + cmd.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.center}><Text style={styles.emptyText}>No terminals found</Text></View>
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
  emptyText: { color: '#64748b', fontSize: 16 },
  statsRow: { flexDirection: 'row', paddingHorizontal: 12, gap: 8, marginBottom: 12 },
  statCard: { flex: 1, borderRadius: 12, padding: 12, alignItems: 'center' },
  statValue: { fontSize: 24, fontWeight: '700' },
  statLabel: { fontSize: 12, color: '#64748b', marginTop: 2 },
  card: { backgroundColor: '#fff', marginHorizontal: 12, marginVertical: 4, padding: 16, borderRadius: 12 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  serialNumber: { fontSize: 16, fontWeight: '700', color: '#1e293b' },
  model: { fontSize: 13, color: '#64748b' },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  metricsRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10, marginBottom: 8 },
  metric: { fontSize: 13, fontWeight: '500' },
  metricLight: { fontSize: 13, color: '#94a3b8' },
  commandRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  cmdBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: '#f1f5f9', alignItems: 'center' },
  cmdBtnDanger: { backgroundColor: '#fef2f2' },
  cmdText: { fontSize: 13, fontWeight: '600', color: '#334155' },
  cmdTextDanger: { color: '#dc2626' },
});

export default POSShellScreen;
