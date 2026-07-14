import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput, Alert,
} from 'react-native';
import { apiClient } from '../api/APIClient';

interface ExportRecord { id: string; filename: string; createdAt: string; size: string; format: string; }

const ACTION_TYPES = ['All', 'login', 'transaction', 'config_change', 'user_action', 'system'];

const AuditExportScreen: React.FC = () => {
  const [fromDate, setFromDate] = useState('2026-04-01');
  const [toDate, setToDate] = useState('2026-04-16');
  const [actionType, setActionType] = useState('All');
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [recentExports, setRecentExports] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const loadRecent = useCallback(async () => {
    try {
      const { data } = await apiClient.get('/audit/exports');
      setRecentExports(data?.exports ?? []);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadRecent(); }, [loadRecent]);

  const preview = async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.post('/audit/export-preview', {
        from: fromDate, to: toDate, actionType: actionType === 'All' ? undefined : actionType,
      });
      setPreviewCount(data?.count ?? 0);
    } catch { Alert.alert('Error', 'Failed to preview'); }
    finally { setLoading(false); }
  };

  const exportLog = async (format: string) => {
    setExporting(true);
    try {
      await apiClient.post('/audit/export', {
        format, from: fromDate, to: toDate, actionType: actionType === 'All' ? undefined : actionType,
      });
      Alert.alert('Success', `${format.toUpperCase()} export started`);
      loadRecent();
    } catch { Alert.alert('Error', 'Export failed'); }
    finally { setExporting(false); }
  };

  return (
    <ScrollView style={s.container}>
      {/* Date Range */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Date Range</Text>
        <View style={s.dateRow}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <Text style={s.fieldLabel}>From</Text>
            <TextInput style={s.input} value={fromDate} onChangeText={setFromDate} placeholder="YYYY-MM-DD" placeholderTextColor="#64748b" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.fieldLabel}>To</Text>
            <TextInput style={s.input} value={toDate} onChangeText={setToDate} placeholder="YYYY-MM-DD" placeholderTextColor="#64748b" />
          </View>
        </View>
      </View>

      {/* Filters */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Filters</Text>
        <Text style={s.fieldLabel}>Action Type</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
          {ACTION_TYPES.map(t => (
            <TouchableOpacity key={t} style={[s.filterChip, actionType === t && s.filterChipActive]} onPress={() => setActionType(t)}>
              <Text style={[s.filterChipText, actionType === t && s.filterChipTextActive]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Preview */}
      <TouchableOpacity style={s.previewBtn} onPress={preview} disabled={loading}>
        <Text style={s.previewBtnText}>{loading ? 'Loading...' : 'Preview Results'}</Text>
      </TouchableOpacity>

      {previewCount !== null && (
        <View style={s.previewCard}>
          <Text style={s.previewValue}>{previewCount.toLocaleString()}</Text>
          <Text style={s.previewLabel}>matching records</Text>
        </View>
      )}

      {/* Export Buttons */}
      <View style={s.exportRow}>
        <TouchableOpacity style={[s.exportBtn, s.csvBtn]} onPress={() => exportLog('csv')} disabled={exporting}>
          <Text style={s.exportBtnText}>Export CSV</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.exportBtn, s.pdfBtn]} onPress={() => exportLog('pdf')} disabled={exporting}>
          <Text style={s.exportBtnText}>Export PDF</Text>
        </TouchableOpacity>
      </View>

      {/* Recent Exports */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Recent Exports</Text>
        {recentExports.length === 0 ? (
          <Text style={s.empty}>No recent exports</Text>
        ) : (
          recentExports.map(exp => (
            <View key={exp.id} style={s.exportRow2}>
              <View style={{ flex: 1 }}>
                <Text style={s.exportName}>{exp.filename}</Text>
                <Text style={s.exportMeta}>{new Date(exp.createdAt).toLocaleDateString()} · {exp.size} · {exp.format.toUpperCase()}</Text>
              </View>
              <TouchableOpacity style={s.downloadBtn}>
                <Text style={s.downloadText}>↓</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  section: { backgroundColor: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 12 },
  sectionTitle: { color: '#f8fafc', fontSize: 16, fontWeight: '600', marginBottom: 12 },
  fieldLabel: { color: '#94a3b8', fontSize: 12, marginBottom: 4 },
  dateRow: { flexDirection: 'row' },
  input: { backgroundColor: '#0f172a', borderRadius: 10, padding: 12, color: '#f8fafc' },
  filterChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#334155', marginRight: 8 },
  filterChipActive: { backgroundColor: '#1d4ed8' },
  filterChipText: { color: '#94a3b8', fontSize: 13 },
  filterChipTextActive: { color: '#fff' },
  previewBtn: { backgroundColor: '#334155', borderRadius: 12, padding: 14, alignItems: 'center', marginBottom: 12 },
  previewBtnText: { color: '#f8fafc', fontSize: 14, fontWeight: '500' },
  previewCard: { backgroundColor: '#1e293b', borderRadius: 12, padding: 20, alignItems: 'center', marginBottom: 12 },
  previewValue: { color: '#3b82f6', fontSize: 28, fontWeight: '700' },
  previewLabel: { color: '#94a3b8', fontSize: 13, marginTop: 4 },
  exportRow: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  exportBtn: { flex: 1, borderRadius: 12, padding: 14, alignItems: 'center' },
  csvBtn: { backgroundColor: '#334155' },
  pdfBtn: { backgroundColor: '#1d4ed8' },
  exportBtnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  empty: { color: '#64748b', textAlign: 'center', padding: 20 },
  exportRow2: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#334155' },
  exportName: { color: '#f8fafc', fontSize: 14, fontWeight: '500' },
  exportMeta: { color: '#64748b', fontSize: 12, marginTop: 2 },
  downloadBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#334155', justifyContent: 'center', alignItems: 'center' },
  downloadText: { color: '#3b82f6', fontSize: 18 },
});

export default AuditExportScreen;
