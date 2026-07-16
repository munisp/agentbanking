import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../lib/APIClient';
const apiClient = new APIClient();

interface QuickAction {
  label: string;
  icon: string;
  screen: string;
  color: string;
}

const quickActions: QuickAction[] = [
  { label: 'Cash In', icon: '⬇️', screen: 'SendMoney', color: '#22c55e' },
  { label: 'Cash Out', icon: '⬆️', screen: 'ReceiveMoney', color: '#f97316' },
  { label: 'Bill Pay', icon: '📄', screen: 'Transactions', color: '#3b82f6' },
  { label: 'Float', icon: '💰', screen: 'Wallet', color: '#a855f7' },
  { label: 'History', icon: '📋', screen: 'TransactionHistory', color: '#14b8a6' },
  { label: 'QR Scan', icon: '📱', screen: 'QRCodeScanner', color: '#6366f1' },
  { label: 'Send', icon: '📤', screen: 'SendMoney', color: '#06b6d4' },
  { label: 'Cards', icon: '💳', screen: 'Cards', color: '#ec4899' },
];

const DashboardScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/dashboard');
      setData(response);
    } catch (error) {
      // Silently handle — dashboard works offline
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Agent Info Card */}
      <View style={styles.agentCard}>
        <View style={styles.agentRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>A</Text>
          </View>
          <View style={styles.agentInfo}>
            <Text style={styles.agentName}>{data?.name || 'Agent'}</Text>
            <Text style={styles.agentCode}>Code: {data?.agentCode || '---'}</Text>
          </View>
          <View style={styles.balanceContainer}>
            <Text style={styles.balanceLabel}>Float Balance</Text>
            <Text style={styles.balanceValue}>₦{data?.floatBalance || '0.00'}</Text>
          </View>
        </View>
      </View>

      {/* Quick Actions Grid */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionGrid}>
        {quickActions.map((action, idx) => (
          <TouchableOpacity
            key={idx}
            style={styles.actionCard}
            onPress={() => navigation.navigate(action.screen)}
          >
            <View style={[styles.actionIcon, { backgroundColor: action.color + '20' }]}>
              <Text style={styles.actionEmoji}>{action.icon}</Text>
            </View>
            <Text style={styles.actionLabel}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Today's Summary */}
      <Text style={styles.sectionTitle}>Today\'s Summary</Text>
      <View style={styles.summaryRow}>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryValue}>{data?.todayTxCount || 0}</Text>
          <Text style={styles.summaryLabel}>Transactions</Text>
        </View>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryValue}>₦{data?.todayVolume || '0'}</Text>
          <Text style={styles.summaryLabel}>Volume</Text>
        </View>
      </View>

      {/* More Features */}
      <Text style={styles.sectionTitle}>More Features</Text>
      <View style={styles.featureList}>
        {[
          { label: 'Exchange Rates', screen: 'ExchangeRates', icon: '💱' },
          { label: 'Savings Goals', screen: 'SavingsGoals', icon: '🎯' },
          { label: 'Referral Program', screen: 'ReferralProgram', icon: '🎁' },
          { label: 'Agent Performance', screen: 'AgentPerformance', icon: '📊' },
          { label: 'Notifications', screen: 'Notifications', icon: '🔔' },
          { label: 'Help & Support', screen: 'Help', icon: '❓' },
        ].map((item, idx) => (
          <TouchableOpacity
            key={idx}
            style={styles.featureItem}
            onPress={() => navigation.navigate(item.screen)}
          >
            <Text style={styles.featureIcon}>{item.icon}</Text>
            <Text style={styles.featureLabel}>{item.label}</Text>
            <Text style={styles.featureArrow}>›</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  agentCard: {
    margin: 16,
    padding: 16,
    backgroundColor: '#1e293b',
    borderRadius: 12,
  },
  agentRow: { flexDirection: 'row', alignItems: 'center' },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#3b82f6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: { color: '#fff', fontSize: 18, fontWeight: 'bold' },
  agentInfo: { flex: 1, marginLeft: 12 },
  agentName: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold' },
  agentCode: { color: '#94a3b8', fontSize: 12, marginTop: 2 },
  balanceContainer: { alignItems: 'flex-end' },
  balanceLabel: { color: '#94a3b8', fontSize: 11 },
  balanceValue: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold' },
  sectionTitle: {
    color: '#f8fafc',
    fontSize: 16,
    fontWeight: 'bold',
    marginHorizontal: 16,
    marginTop: 20,
    marginBottom: 12,
  },
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
  },
  actionCard: {
    width: '25%',
    alignItems: 'center',
    paddingVertical: 12,
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionEmoji: { fontSize: 22 },
  actionLabel: { color: '#cbd5e1', fontSize: 11, marginTop: 6, fontWeight: '500' },
  summaryRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 12 },
  summaryCard: {
    flex: 1,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
  },
  summaryValue: { color: '#f8fafc', fontSize: 20, fontWeight: 'bold' },
  summaryLabel: { color: '#94a3b8', fontSize: 12, marginTop: 4 },
  featureList: { marginHorizontal: 16 },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  featureIcon: { fontSize: 20, marginRight: 12 },
  featureLabel: { flex: 1, color: '#f8fafc', fontSize: 14 },
  featureArrow: { color: '#64748b', fontSize: 20 },
});

export default DashboardScreen;
