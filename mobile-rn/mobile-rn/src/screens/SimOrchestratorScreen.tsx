import React, { useState, useMemo } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Switch, Platform,
} from 'react-native';

/**
 * SIM Orchestrator Screen — Multi-network provider management for POS terminals.
 *
 * Features (parity with PWA SimOrchestratorTab + Flutter sim_orchestrator_screen):
 *   1. Per-slot signal strength with carrier color coding
 *   2. Active SIM slot indicator with score badge
 *   3. Carrier ranking table with SLA data
 *   4. Failover history timeline
 *   5. Transaction-type-aware recommendations
 *   6. USSD quick-dial for balance checks
 *   7. Failover policy configuration
 */

interface SimSlot {
  index: number;
  carrier: string;
  name: string;
  signalDbm: number;
  networkType: string;
  isPreferred: boolean;
  score: number;
  iccid: string;
}

interface CarrierRank {
  carrier: string;
  reliability: number;
  latency: number;
  cost: number;
  sla: number;
  rank: number;
  financialPref: boolean;
}

interface FailoverEvent {
  from: string;
  to: string;
  reason: string;
  time: Date;
}

const CARRIER_COLORS: Record<string, string> = {
  MTN: '#D4A843',
  AIRTEL: '#E05555',
  GLO: '#4CAF50',
  '9MOBILE': '#4A90D9',
};

const USSD_COMMANDS = [
  { carrier: 'MTN', balance: '*556#', data: '*131*4#' },
  { carrier: 'AIRTEL', balance: '*123#', data: '*140#' },
  { carrier: 'GLO', balance: '*124#', data: '*127*0#' },
  { carrier: '9MOBILE', balance: '*232#', data: '*229*0#' },
];

const TX_TYPES = ['general', 'financial', 'payment', 'transfer', 'settlement', 'telemetry'];

function signalLabel(dbm: number): { label: string; color: string } {
  if (dbm >= -65) return { label: 'Excellent', color: '#4CAF50' };
  if (dbm >= -75) return { label: 'Good', color: '#4A90D9' };
  if (dbm >= -85) return { label: 'Fair', color: '#D4A843' };
  return { label: 'Poor', color: '#E05555' };
}

function formatTime(time: Date): string {
  const diff = Date.now() - time.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function SimOrchestratorScreen() {
  const [activeTab, setActiveTab] = useState<'slots' | 'rankings' | 'history' | 'policy'>('slots');
  const [selectedTxType, setSelectedTxType] = useState('general');
  const [autoFailover, setAutoFailover] = useState(true);
  const [minSignalDbm, setMinSignalDbm] = useState(-90);

  const slots: SimSlot[] = useMemo(() => [
    { index: 0, carrier: 'MTN', name: 'MTN Nigeria', signalDbm: -65, networkType: '4G', isPreferred: true, score: 82, iccid: '89234...001' },
    { index: 1, carrier: 'AIRTEL', name: 'Airtel Nigeria', signalDbm: -75, networkType: '4G', isPreferred: false, score: 71, iccid: '89234...002' },
    { index: 2, carrier: 'GLO', name: 'Globacom', signalDbm: -88, networkType: '3G', isPreferred: false, score: 48, iccid: '89234...003' },
  ], []);

  const rankings: CarrierRank[] = useMemo(() => [
    { carrier: 'MTN', reliability: 92, latency: 45, cost: 0.35, sla: 99.5, rank: 1, financialPref: true },
    { carrier: 'AIRTEL', reliability: 88, latency: 55, cost: 0.30, sla: 99.0, rank: 2, financialPref: true },
    { carrier: 'GLO', reliability: 82, latency: 65, cost: 0.25, sla: 98.0, rank: 3, financialPref: false },
    { carrier: '9MOBILE', reliability: 78, latency: 70, cost: 0.28, sla: 97.5, rank: 4, financialPref: false },
  ], []);

  const history: FailoverEvent[] = useMemo(() => [
    { from: 'GLO', to: 'MTN', reason: 'signal -95dBm < -90dBm', time: new Date(Date.now() - 2 * 3600000) },
    { from: 'AIRTEL', to: 'MTN', reason: 'latency 650ms > 500ms', time: new Date(Date.now() - 8 * 3600000) },
  ], []);

  const recommendation = useMemo(() => {
    const isFinancial = ['financial', 'payment', 'transfer', 'settlement'].includes(selectedTxType);
    return isFinancial
      ? 'MTN recommended: 92% reliability, 99.5% SLA'
      : 'GLO recommended: best cost/performance (₦0.25/MB)';
  }, [selectedTxType]);

  return (
    <View style={styles.container}>
      {/* Tab Bar */}
      <View style={styles.tabBar}>
        {(['slots', 'rankings', 'history', 'policy'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.content}>
        {activeTab === 'slots' && (
          <>
            {/* Terminal ID */}
            <View style={styles.card}>
              <Text style={styles.monoText}>TERM-001</Text>
              <View style={styles.onlineBadge}>
                <Text style={styles.onlineText}>Online</Text>
              </View>
            </View>

            {/* SIM Slots */}
            {slots.map(slot => (
              <View key={slot.index} style={[styles.card, slot.isPreferred && styles.cardActive]}>
                <View style={styles.slotRow}>
                  <View style={[styles.slotBadge, { borderColor: CARRIER_COLORS[slot.carrier] ?? '#666' }]}>
                    <Text style={[styles.slotBadgeText, { color: CARRIER_COLORS[slot.carrier] ?? '#666' }]}>
                      SIM{slot.index + 1}
                    </Text>
                    {slot.isPreferred && <Text style={styles.checkMark}>●</Text>}
                  </View>
                  <View style={styles.slotInfo}>
                    <Text style={[styles.carrierName, { color: CARRIER_COLORS[slot.carrier] ?? '#ccc' }]}>{slot.name}</Text>
                    <Text style={{ color: signalLabel(slot.signalDbm).color, fontSize: 12 }}>
                      {slot.networkType} · {slot.signalDbm} dBm · {signalLabel(slot.signalDbm).label}
                    </Text>
                  </View>
                  <View style={[styles.scoreBadge, { backgroundColor: slot.score > 70 ? '#1B3D1B' : '#3D3D1B' }]}>
                    <Text style={{ color: slot.score > 70 ? '#4CAF50' : '#D4A843', fontWeight: 'bold' }}>{slot.score}</Text>
                  </View>
                </View>
              </View>
            ))}

            {/* Recommendation */}
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Recommendation</Text>
              <View style={styles.txTypeRow}>
                {TX_TYPES.map(t => (
                  <TouchableOpacity
                    key={t}
                    style={[styles.txTypeChip, selectedTxType === t && styles.txTypeChipActive]}
                    onPress={() => setSelectedTxType(t)}
                  >
                    <Text style={[styles.txTypeText, selectedTxType === t && styles.txTypeTextActive]}>{t}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={styles.recommendationText}>{recommendation}</Text>
            </View>
          </>
        )}

        {activeTab === 'rankings' && (
          <>
            <Text style={styles.pageTitle}>Carrier Rankings (Nigeria)</Text>
            {rankings.map(r => (
              <View key={r.carrier} style={styles.card}>
                <View style={styles.slotRow}>
                  <View style={[styles.rankBadge, { backgroundColor: (CARRIER_COLORS[r.carrier] ?? '#666') + '33' }]}>
                    <Text style={styles.rankText}>#{r.rank}</Text>
                  </View>
                  <View style={styles.slotInfo}>
                    <Text style={[styles.carrierName, { color: CARRIER_COLORS[r.carrier] ?? '#ccc' }]}>{r.carrier}</Text>
                    <Text style={styles.dimText}>{r.reliability}% reliable · {r.latency}ms · ₦{r.cost}/MB</Text>
                  </View>
                  {r.financialPref && (
                    <View style={styles.financialBadge}>
                      <Text style={styles.financialBadgeText}>Financial</Text>
                    </View>
                  )}
                </View>
              </View>
            ))}
          </>
        )}

        {activeTab === 'history' && (
          <>
            <Text style={styles.pageTitle}>Failover History</Text>
            {history.map((e, i) => (
              <View key={i} style={styles.card}>
                <View style={styles.slotRow}>
                  <Text style={{ color: CARRIER_COLORS[e.from] ?? '#ccc', fontWeight: 'bold' }}>{e.from}</Text>
                  <Text style={styles.dimText}> → </Text>
                  <Text style={{ color: CARRIER_COLORS[e.to] ?? '#ccc', fontWeight: 'bold' }}>{e.to}</Text>
                  <View style={{ flex: 1 }} />
                  <Text style={styles.dimText}>{formatTime(e.time)}</Text>
                </View>
                <Text style={{ color: '#D4A843', fontSize: 12, marginTop: 4 }}>{e.reason}</Text>
              </View>
            ))}
          </>
        )}

        {activeTab === 'policy' && (
          <>
            <Text style={styles.pageTitle}>Failover Policy</Text>
            <View style={styles.card}>
              <View style={styles.slotRow}>
                <Text style={styles.sectionTitle}>Auto Failover</Text>
                <Switch value={autoFailover} onValueChange={setAutoFailover} />
              </View>
            </View>
            <View style={styles.card}>
              <Text style={styles.dimText}>Min Signal: {minSignalDbm} dBm</Text>
            </View>

            <Text style={[styles.pageTitle, { marginTop: 16 }]}>USSD Quick Dial</Text>
            {USSD_COMMANDS.map(c => (
              <View key={c.carrier} style={styles.card}>
                <View style={styles.slotRow}>
                  <Text style={{ color: CARRIER_COLORS[c.carrier] ?? '#ccc', fontWeight: 'bold', width: 72 }}>{c.carrier}</Text>
                  <Text style={styles.monoText}>Balance: {c.balance}</Text>
                  <View style={{ flex: 1 }} />
                  <Text style={styles.monoText}>Data: {c.data}</Text>
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0E1A' },
  tabBar: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: '#1E2A3E', paddingTop: Platform.OS === 'ios' ? 48 : 8 },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#4A90D9' },
  tabText: { color: '#666', fontSize: 13 },
  tabTextActive: { color: '#fff' },
  content: { flex: 1, padding: 16 },
  card: { backgroundColor: '#141B2D', borderRadius: 10, borderWidth: 1, borderColor: '#1E2A3E', padding: 14, marginBottom: 10 },
  cardActive: { borderColor: '#4A90D9', borderWidth: 2 },
  slotRow: { flexDirection: 'row', alignItems: 'center' },
  slotBadge: { width: 44, height: 44, borderRadius: 10, borderWidth: 1, justifyContent: 'center', alignItems: 'center' },
  slotBadgeText: { fontSize: 10, fontWeight: 'bold' },
  checkMark: { color: '#4CAF50', fontSize: 8, marginTop: 2 },
  slotInfo: { flex: 1, marginLeft: 10 },
  carrierName: { fontWeight: 'bold', fontSize: 14 },
  scoreBadge: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  rankBadge: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  rankText: { color: '#fff', fontSize: 11, fontWeight: 'bold' },
  financialBadge: { backgroundColor: '#1B3D1B', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  financialBadgeText: { color: '#4CAF50', fontSize: 10 },
  sectionTitle: { color: '#fff', fontWeight: 'bold', fontSize: 15 },
  pageTitle: { color: '#fff', fontSize: 18, fontWeight: 'bold', marginBottom: 12 },
  dimText: { color: '#888', fontSize: 12 },
  monoText: { color: '#888', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 12 },
  onlineBadge: { backgroundColor: '#1B3D1B', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, position: 'absolute', right: 14, top: 14 },
  onlineText: { color: '#4CAF50', fontSize: 12 },
  txTypeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, marginBottom: 8 },
  txTypeChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, backgroundColor: '#1E2A3E' },
  txTypeChipActive: { backgroundColor: '#4A90D933' },
  txTypeText: { color: '#888', fontSize: 11 },
  txTypeTextActive: { color: '#4A90D9' },
  recommendationText: { color: '#4A90D9', fontSize: 13, marginTop: 4 },
});
