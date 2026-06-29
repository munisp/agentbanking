import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Switch, TouchableOpacity, Alert } from 'react-native';
import { apiClient } from '../api/APIClient';

interface ChannelPrefs { push: boolean; sms: boolean; email: boolean; }
interface Section { title: string; key: string; prefs: ChannelPrefs; }

const DEFAULT_SECTIONS: Section[] = [
  { title: 'Transaction Alerts', key: 'transaction', prefs: { push: true, sms: true, email: false } },
  { title: 'Security Alerts', key: 'security', prefs: { push: true, sms: true, email: true } },
  { title: 'Performance Updates', key: 'performance', prefs: { push: true, sms: false, email: false } },
  { title: 'System Notifications', key: 'system', prefs: { push: true, sms: false, email: false } },
];

const NotificationPreferencesScreen: React.FC = () => {
  const [sections, setSections] = useState<Section[]>(DEFAULT_SECTIONS);
  const [quietStart, setQuietStart] = useState('22:00');
  const [quietEnd, setQuietEnd] = useState('07:00');
  const [saving, setSaving] = useState(false);

  const toggle = (sectionKey: string, channel: keyof ChannelPrefs) => {
    setSections(prev => prev.map(s =>
      s.key === sectionKey ? { ...s, prefs: { ...s.prefs, [channel]: !s.prefs[channel] } } : s,
    ));
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = { channels: Object.fromEntries(sections.map(s => [s.key, s.prefs])), quietHours: { start: quietStart, end: quietEnd } };
      await apiClient.put('/notifications/preferences', payload);
      Alert.alert('Saved', 'Notification preferences updated');
    } catch { Alert.alert('Error', 'Failed to save preferences'); }
    finally { setSaving(false); }
  };

  const testNotification = async () => {
    try { await apiClient.post('/notifications/test', {}); Alert.alert('Sent', 'Test notification sent'); }
    catch { Alert.alert('Error', 'Failed to send test notification'); }
  };

  return (
    <ScrollView style={s.container}>
      {sections.map(section => (
        <View key={section.key} style={s.section}>
          <Text style={s.sectionTitle}>{section.title}</Text>
          {(['push', 'sms', 'email'] as const).map(ch => (
            <View key={ch} style={s.row}>
              <Text style={s.channelLabel}>{ch.charAt(0).toUpperCase() + ch.slice(1)}</Text>
              <Switch
                value={section.prefs[ch]}
                onValueChange={() => toggle(section.key, ch)}
                trackColor={{ false: '#334155', true: '#1d4ed8' }}
                thumbColor={section.prefs[ch] ? '#3b82f6' : '#64748b'}
              />
            </View>
          ))}
        </View>
      ))}

      {/* Quiet Hours */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Quiet Hours</Text>
        <View style={s.row}><Text style={s.channelLabel}>Start</Text><Text style={s.timeValue}>{quietStart}</Text></View>
        <View style={s.row}><Text style={s.channelLabel}>End</Text><Text style={s.timeValue}>{quietEnd}</Text></View>
      </View>

      {/* Test */}
      <TouchableOpacity style={s.testBtn} onPress={testNotification}>
        <Text style={s.testBtnText}>Send Test Notification</Text>
      </TouchableOpacity>

      {/* Save */}
      <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving}>
        <Text style={s.saveBtnText}>{saving ? 'Saving...' : 'Save Preferences'}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
  section: { backgroundColor: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 12 },
  sectionTitle: { color: '#f8fafc', fontSize: 16, fontWeight: '600', marginBottom: 12 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#334155' },
  channelLabel: { color: '#cbd5e1', fontSize: 14 },
  timeValue: { color: '#3b82f6', fontSize: 14, fontWeight: '600' },
  testBtn: { backgroundColor: '#334155', borderRadius: 12, padding: 14, alignItems: 'center', marginBottom: 12 },
  testBtnText: { color: '#94a3b8', fontSize: 14, fontWeight: '500' },
  saveBtn: { backgroundColor: '#1d4ed8', borderRadius: 12, padding: 16, alignItems: 'center', marginBottom: 40 },
  saveBtnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});

export default NotificationPreferencesScreen;
