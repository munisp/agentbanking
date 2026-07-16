import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, Switch, Modal, TextInput, Alert,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface Schedule {
  id: string; name: string; severity: string; startTime: string; endTime: string;
  weekdays: number[]; enabled: boolean;
}

const SEVERITY_COLORS: Record<string, string> = { critical: '#dc2626', high: '#f97316', medium: '#eab308', low: '#22c55e' };
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const ComplianceSchedulingScreen: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', severity: 'medium', startTime: '09:00', endTime: '17:00', weekdays: [1,2,3,4,5], enabled: true });

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get('/compliance/schedules');
      setSchedules(data?.schedules ?? []);
    } catch (e) { console.error(e); } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleDay = (d: number) => {
    setForm(prev => ({
      ...prev,
      weekdays: prev.weekdays.includes(d) ? prev.weekdays.filter(x => x !== d) : [...prev.weekdays, d],
    }));
  };

  const submit = async () => {
    try {
      await apiClient.post('/compliance/schedules', form);
      setShowModal(false);
      load();
      Alert.alert('Success', 'Schedule created');
    } catch { Alert.alert('Error', 'Failed to create schedule'); }
  };

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;

  return (
    <View style={s.container}>
      <View style={s.summaryCard}>
        <Text style={s.summaryValue}>{schedules.filter(s => s.enabled).length}</Text>
        <Text style={s.summaryLabel}>Active Policies</Text>
      </View>

      <FlatList
        data={schedules}
        keyExtractor={item => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#3b82f6" />}
        renderItem={({ item }) => (
          <View style={s.card}>
            <View style={s.cardHeader}>
              <Text style={s.cardTitle}>{item.name}</Text>
              <View style={[s.severityBadge, { backgroundColor: SEVERITY_COLORS[item.severity] ?? '#64748b' }]}>
                <Text style={s.severityText}>{item.severity}</Text>
              </View>
            </View>
            <Text style={s.timeWindow}>{item.startTime} — {item.endTime}</Text>
            <View style={s.daysRow}>
              {DAYS.map((d, i) => (
                <View key={d} style={[s.dayPill, item.weekdays.includes(i + 1) && s.dayPillActive]}>
                  <Text style={[s.dayText, item.weekdays.includes(i + 1) && s.dayTextActive]}>{d}</Text>
                </View>
              ))}
            </View>
            <View style={s.enabledRow}>
              <Text style={s.enabledLabel}>Enabled</Text>
              <Switch value={item.enabled} trackColor={{ false: '#334155', true: '#1d4ed8' }} thumbColor={item.enabled ? '#3b82f6' : '#64748b'} />
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={s.empty}>No compliance schedules</Text>}
      />

      <TouchableOpacity style={s.fab} onPress={() => setShowModal(true)}>
        <Text style={s.fabText}>+ Add Schedule</Text>
      </TouchableOpacity>

      {/* Add Modal */}
      <Modal visible={showModal} transparent animationType="slide">
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <Text style={s.modalTitle}>New Compliance Schedule</Text>
            <TextInput style={s.input} placeholder="Policy Name" placeholderTextColor="#64748b" value={form.name} onChangeText={t => setForm(p => ({ ...p, name: t }))} />
            <View style={s.severityRow}>
              {['critical', 'high', 'medium', 'low'].map(sev => (
                <TouchableOpacity key={sev} style={[s.sevChip, form.severity === sev && { backgroundColor: SEVERITY_COLORS[sev] }]} onPress={() => setForm(p => ({ ...p, severity: sev }))}>
                  <Text style={s.sevChipText}>{sev}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={s.timeRow}>
              <TextInput style={[s.input, { flex: 1, marginRight: 8 }]} placeholder="Start (HH:MM)" placeholderTextColor="#64748b" value={form.startTime} onChangeText={t => setForm(p => ({ ...p, startTime: t }))} />
              <TextInput style={[s.input, { flex: 1 }]} placeholder="End (HH:MM)" placeholderTextColor="#64748b" value={form.endTime} onChangeText={t => setForm(p => ({ ...p, endTime: t }))} />
            </View>
            <View style={s.daysRow}>
              {DAYS.map((d, i) => (
                <TouchableOpacity key={d} style={[s.dayPill, form.weekdays.includes(i + 1) && s.dayPillActive]} onPress={() => toggleDay(i + 1)}>
                  <Text style={[s.dayText, form.weekdays.includes(i + 1) && s.dayTextActive]}>{d}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={s.modalActions}>
              <TouchableOpacity style={s.cancelBtn} onPress={() => setShowModal(false)}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={s.submitBtn} onPress={submit}><Text style={s.submitText}>Create</Text></TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  summaryCard: { backgroundColor: '#1e293b', borderRadius: 12, padding: 20, alignItems: 'center', marginBottom: 16 },
  summaryValue: { color: '#3b82f6', fontSize: 32, fontWeight: '700' },
  summaryLabel: { color: '#94a3b8', fontSize: 14, marginTop: 4 },
  card: { backgroundColor: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 10 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  cardTitle: { color: '#f8fafc', fontSize: 16, fontWeight: '600' },
  severityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  severityText: { color: '#fff', fontSize: 11, fontWeight: '700', textTransform: 'capitalize' },
  timeWindow: { color: '#94a3b8', fontSize: 13, marginBottom: 8 },
  daysRow: { flexDirection: 'row', gap: 4, marginBottom: 8, flexWrap: 'wrap' },
  dayPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: '#334155' },
  dayPillActive: { backgroundColor: '#1d4ed8' },
  dayText: { color: '#64748b', fontSize: 12 },
  dayTextActive: { color: '#fff' },
  enabledRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  enabledLabel: { color: '#94a3b8', fontSize: 13 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40 },
  fab: { position: 'absolute', bottom: 24, right: 24, backgroundColor: '#1d4ed8', borderRadius: 28, paddingHorizontal: 20, paddingVertical: 14, elevation: 4 },
  fabText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#1e293b', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24 },
  modalTitle: { color: '#f8fafc', fontSize: 18, fontWeight: '700', marginBottom: 16 },
  input: { backgroundColor: '#0f172a', borderRadius: 10, padding: 12, color: '#f8fafc', marginBottom: 12 },
  severityRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  sevChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#334155' },
  sevChipText: { color: '#fff', fontSize: 13, textTransform: 'capitalize' },
  timeRow: { flexDirection: 'row', marginBottom: 12 },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 12, marginTop: 8 },
  cancelBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10, backgroundColor: '#334155' },
  cancelText: { color: '#94a3b8', fontSize: 14 },
  submitBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10, backgroundColor: '#1d4ed8' },
  submitText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});

export default ComplianceSchedulingScreen;
