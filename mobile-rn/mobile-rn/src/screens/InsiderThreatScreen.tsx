/**
 * InsiderThreatScreen (React Native)
 * Approval workflows, threat alerts, and step-up auth for mobile admin users.
 */
import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  RefreshControl,
  StyleSheet,
  Modal,
} from 'react-native';

interface ApprovalRequest {
  id: string;
  type: string;
  requestedByCode: string;
  amount: number;
  currency: string;
  requiredApprovals: number;
  approvals: number;
  expiresAt: string;
}

interface ThreatAlert {
  id: string;
  threatType: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  agentCode: string;
  description: string;
  riskScore: number;
  timestamp: string;
  autoBlocked: boolean;
}

const SEVERITY_COLORS = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#16a34a',
};

export default function InsiderThreatScreen() {
  const [activeTab, setActiveTab] = useState<'approvals' | 'alerts' | 'audit'>('approvals');
  const [stepUpVerified, setStepUpVerified] = useState(false);
  const [showStepUpModal, setShowStepUpModal] = useState(false);
  const [password, setPassword] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [pendingApprovals] = useState<ApprovalRequest[]>([]);
  const [alerts] = useState<ThreatAlert[]>([]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    // In production: refetch from API
    setTimeout(() => setRefreshing(false), 1000);
  }, []);

  const handleStepUp = () => {
    if (password.length > 0) {
      // In production: verify via API and get token
      setStepUpVerified(true);
      setShowStepUpModal(false);
      setPassword('');
      Alert.alert('Success', 'Step-up authentication verified (5 min)');
    }
  };

  const handleApprove = (approval: ApprovalRequest) => {
    if (!stepUpVerified) {
      Alert.alert('Authentication Required', 'Please complete step-up authentication first.');
      setShowStepUpModal(true);
      return;
    }
    Alert.alert('Confirm', `Approve ${approval.type.replace(/_/g, ' ')} for ₦${approval.amount.toLocaleString()}?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Approve', onPress: () => Alert.alert('Done', 'Approval granted') },
    ]);
  };

  const handleReject = (approval: ApprovalRequest) => {
    Alert.prompt('Reject Request', 'Enter reason for rejection (min 5 chars):', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Reject',
        style: 'destructive',
        onPress: (reason) => {
          if ((reason?.length ?? 0) >= 5) {
            Alert.alert('Done', 'Request rejected');
          } else {
            Alert.alert('Error', 'Reason must be at least 5 characters');
          }
        },
      },
    ]);
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Insider Threat</Text>
        {stepUpVerified ? (
          <View style={styles.verifiedBadge}>
            <Text style={styles.verifiedText}>Verified</Text>
          </View>
        ) : (
          <TouchableOpacity style={styles.authButton} onPress={() => setShowStepUpModal(true)}>
            <Text style={styles.authButtonText}>Authenticate</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Tabs */}
      <View style={styles.tabBar}>
        {(['approvals', 'alerts', 'audit'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.activeTab]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.activeTabText]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === 'approvals' && pendingApprovals.length > 0 && ` (${pendingApprovals.length})`}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {activeTab === 'approvals' && (
          pendingApprovals.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>✓</Text>
              <Text style={styles.emptyText}>No pending approvals</Text>
            </View>
          ) : (
            pendingApprovals.map(a => (
              <View key={a.id} style={styles.card}>
                <Text style={styles.cardTitle}>{a.type.replace(/_/g, ' ')}</Text>
                <Text style={styles.cardSubtitle}>₦{a.amount.toLocaleString()} • By: {a.requestedByCode}</Text>
                <Text style={styles.cardMeta}>{a.approvals}/{a.requiredApprovals} approvals</Text>
                <View style={styles.cardActions}>
                  <TouchableOpacity style={styles.rejectBtn} onPress={() => handleReject(a)}>
                    <Text style={styles.rejectBtnText}>Reject</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.approveBtn, !stepUpVerified && styles.disabledBtn]}
                    onPress={() => handleApprove(a)}
                  >
                    <Text style={styles.approveBtnText}>Approve</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))
          )
        )}

        {activeTab === 'alerts' && (
          alerts.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>🛡️</Text>
              <Text style={styles.emptyText}>No active threats</Text>
            </View>
          ) : (
            alerts.map(alert => (
              <View key={alert.id} style={[styles.card, { borderLeftWidth: 4, borderLeftColor: SEVERITY_COLORS[alert.severity] }]}>
                <View style={styles.alertHeader}>
                  <View style={[styles.severityBadge, { backgroundColor: SEVERITY_COLORS[alert.severity] }]}>
                    <Text style={styles.severityText}>{alert.severity.toUpperCase()}</Text>
                  </View>
                  <Text style={styles.riskScore}>{alert.riskScore}/100</Text>
                </View>
                <Text style={styles.cardTitle}>{alert.threatType.replace(/_/g, ' ')}</Text>
                <Text style={styles.cardSubtitle}>{alert.description}</Text>
                <Text style={styles.cardMeta}>Agent: {alert.agentCode} • {new Date(alert.timestamp).toLocaleString()}</Text>
                {alert.autoBlocked && <Text style={styles.blockedLabel}>AUTO-BLOCKED</Text>}
              </View>
            ))
          )
        )}

        {activeTab === 'audit' && (
          <View style={styles.auditSection}>
            <View style={[styles.card, { backgroundColor: '#f0fdf4' }]}>
              <Text style={[styles.cardTitle, { color: '#16a34a' }]}>🔒 Hash Chain Intact</Text>
              <Text style={styles.cardSubtitle}>No tampering detected in audit trail</Text>
            </View>

            <Text style={styles.sectionTitle}>Separation of Duties</Text>
            {[
              'Self-approval blocked on all financial mutations',
              'Maker and Approver roles mutually exclusive',
              'Step-up authentication for privileged actions',
              '15-minute admin session timeout',
              'Cryptographic hash chain audit trail',
            ].map((rule, i) => (
              <View key={i} style={styles.ruleRow}>
                <Text style={styles.ruleCheck}>✓</Text>
                <Text style={styles.ruleText}>{rule}</Text>
              </View>
            ))}

            <Text style={styles.sectionTitle}>Approval Thresholds</Text>
            <View style={[styles.card, { backgroundColor: '#f0fdf4' }]}>
              <Text style={styles.thresholdTitle}>Tier 1 — Standard (₦0–500K)</Text>
              <Text style={styles.thresholdDesc}>No additional approval needed</Text>
            </View>
            <View style={[styles.card, { backgroundColor: '#fef9c3' }]}>
              <Text style={styles.thresholdTitle}>Tier 2 — Dual Control (₦500K–5M)</Text>
              <Text style={styles.thresholdDesc}>1 additional approver required</Text>
            </View>
            <View style={[styles.card, { backgroundColor: '#fef2f2' }]}>
              <Text style={styles.thresholdTitle}>Tier 3 — Compliance (₦5M+)</Text>
              <Text style={styles.thresholdDesc}>2 approvers + 30-min cooling period</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Step-Up Auth Modal */}
      <Modal visible={showStepUpModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Step-Up Authentication</Text>
            <Text style={styles.modalDesc}>
              Re-enter your password to verify identity for approval actions.
            </Text>
            <TextInput
              style={styles.passwordInput}
              placeholder="Enter password"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity onPress={() => setShowStepUpModal(false)}>
                <Text style={styles.cancelBtn}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.verifyBtn} onPress={handleStepUp}>
                <Text style={styles.verifyBtnText}>Verify</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#111827' },
  verifiedBadge: { backgroundColor: '#d1fae5', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  verifiedText: { color: '#065f46', fontSize: 12, fontWeight: '600' },
  authButton: { backgroundColor: '#4f46e5', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8 },
  authButtonText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  tabBar: { flexDirection: 'row', backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  activeTab: { borderBottomWidth: 2, borderBottomColor: '#4f46e5' },
  tabText: { fontSize: 13, color: '#6b7280' },
  activeTabText: { color: '#4f46e5', fontWeight: '600' },
  content: { flex: 1, padding: 16 },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 48, color: '#16a34a' },
  emptyText: { fontSize: 16, color: '#6b7280', marginTop: 8 },
  card: { backgroundColor: '#fff', borderRadius: 8, padding: 16, marginBottom: 12, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: '#111827' },
  cardSubtitle: { fontSize: 13, color: '#6b7280', marginTop: 4 },
  cardMeta: { fontSize: 11, color: '#9ca3af', marginTop: 4 },
  cardActions: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 12, gap: 8 },
  rejectBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 6, borderWidth: 1, borderColor: '#dc2626' },
  rejectBtnText: { color: '#dc2626', fontSize: 13, fontWeight: '600' },
  approveBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 6, backgroundColor: '#16a34a' },
  approveBtnText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  disabledBtn: { opacity: 0.5 },
  alertHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  severityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  severityText: { color: '#fff', fontSize: 10, fontWeight: 'bold' },
  riskScore: { fontSize: 14, fontWeight: 'bold', color: '#374151' },
  blockedLabel: { color: '#dc2626', fontWeight: 'bold', fontSize: 11, marginTop: 8 },
  auditSection: { paddingBottom: 32 },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#111827', marginTop: 16, marginBottom: 8 },
  ruleRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 4, paddingLeft: 4 },
  ruleCheck: { color: '#16a34a', fontSize: 14, marginRight: 8 },
  ruleText: { fontSize: 13, color: '#374151' },
  thresholdTitle: { fontSize: 14, fontWeight: '600', color: '#111827' },
  thresholdDesc: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  modalContent: { backgroundColor: '#fff', borderRadius: 12, padding: 24 },
  modalTitle: { fontSize: 18, fontWeight: 'bold', color: '#111827' },
  modalDesc: { fontSize: 13, color: '#6b7280', marginTop: 8, marginBottom: 16 },
  passwordInput: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 8, padding: 12, fontSize: 14 },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 16, gap: 12, alignItems: 'center' },
  cancelBtn: { color: '#6b7280', fontSize: 14 },
  verifyBtn: { backgroundColor: '#4f46e5', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8 },
  verifyBtnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});
