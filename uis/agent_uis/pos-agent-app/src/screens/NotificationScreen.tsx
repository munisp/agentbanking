import React, { useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

type NotificationType = 'transaction' | 'alert' | 'system' | 'promotion' | 'kyc';

type AppNotification = {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  timestamp: Date;
  isRead: boolean;
  actionRoute?: string;
};

const TYPE_META: Record<NotificationType, { icon: string; color: string; label: string }> = {
  transaction: { icon: '⇄', color: '#3B82F6', label: 'Transaction' },
  alert:       { icon: '⚠', color: '#F59E0B', label: 'Alert' },
  system:      { icon: '↻', color: '#6B7280', label: 'System' },
  promotion:   { icon: '⊕', color: '#10B981', label: 'Promotion' },
  kyc:         { icon: '✓', color: '#8B5CF6', label: 'KYC' },
};

function fmt(d: Date): string {
  const diff = Date.now() - d.getTime();
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

const INITIAL: AppNotification[] = [
  { id: 'n1', type: 'transaction', title: 'Cash-In Successful', body: 'NGN 50,000 deposited to account ending 4521. Reference: TXN-20240412-001', timestamp: new Date(Date.now() - 5 * 60000), isRead: false, actionRoute: 'TransactionHistory' },
  { id: 'n2', type: 'alert', title: 'Low Float Balance', body: 'Your float balance is NGN 12,500 — below the recommended NGN 25,000 threshold.', timestamp: new Date(Date.now() - 3600000), isRead: false, actionRoute: 'FloatManagement' },
  { id: 'n3', type: 'kyc', title: 'KYC Verification Required', body: 'Customer John Doe (BVN: 2234****890) requires identity re-verification.', timestamp: new Date(Date.now() - 3 * 3600000), isRead: true, actionRoute: 'KYC' },
  { id: 'n4', type: 'system', title: 'App Update Available', body: '54Link v2.5.1 is available. New features: rate lock, biometric login, and improved offline sync.', timestamp: new Date(Date.now() - 86400000), isRead: true },
  { id: 'n5', type: 'promotion', title: 'Bonus Commission This Week', body: 'Earn 1.5x commission on all international transfers until Sunday. T&Cs apply.', timestamp: new Date(Date.now() - 2 * 86400000), isRead: false, actionRoute: 'SendMoney' },
  { id: 'n6', type: 'transaction', title: 'Transfer Completed', body: 'NGN 25,000 sent to Fatima Abubakar (GTBank ****7890). Commission: NGN 125.', timestamp: new Date(Date.now() - 3 * 86400000), isRead: true, actionRoute: 'TransactionHistory' },
];

const FILTERS: (NotificationType | null)[] = [null, 'transaction', 'alert', 'system', 'promotion', 'kyc'];

export default function NotificationScreen() {
  const navigation = useNavigation<any>();
  const [items, setItems] = useState<AppNotification[]>(INITIAL);
  const [activeTab, setActiveTab] = useState<'all' | 'unread'>('all');
  const [filter, setFilter] = useState<NotificationType | null>(null);

  const unread = items.filter(n => !n.isRead);
  const displayed = (activeTab === 'unread' ? unread : items)
    .filter(n => filter === null || n.type === filter);

  const markRead = (id: string) =>
    setItems(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
  const markAllRead = () =>
    setItems(prev => prev.map(n => ({ ...n, isRead: true })));
  const remove = (id: string) =>
    setItems(prev => prev.filter(n => n.id !== id));
  const clearAll = () =>
    Alert.alert('Clear All', 'Remove all notifications?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: () => setItems([]) },
    ]);

  const renderItem = ({ item }: { item: AppNotification }) => {
    const meta = TYPE_META[item.type];
    return (
      <TouchableOpacity
        style={[styles.tile, !item.isRead && { backgroundColor: meta.color + '0D' }]}
        onPress={() => {
          markRead(item.id);
          if (item.actionRoute) navigation.navigate(item.actionRoute as never);
        }}
        onLongPress={() =>
          Alert.alert('Remove', 'Delete this notification?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: () => remove(item.id) },
          ])
        }
      >
        <View style={[styles.iconBadge, { backgroundColor: meta.color + '26' }]}>
          <Text style={[styles.iconText, { color: meta.color }]}>{meta.icon}</Text>
        </View>
        <View style={styles.tileContent}>
          <View style={styles.tileRow}>
            <Text style={[styles.tileTitle, !item.isRead && styles.tileTitleBold]} numberOfLines={1}>
              {item.title}
            </Text>
            {!item.isRead && <View style={[styles.dot, { backgroundColor: meta.color }]} />}
          </View>
          <Text style={styles.tileBody} numberOfLines={2}>{item.body}</Text>
          <View style={styles.tileFooter}>
            <View style={[styles.typeBadge, { backgroundColor: meta.color + '26' }]}>
              <Text style={[styles.typeBadgeText, { color: meta.color }]}>{meta.label}</Text>
            </View>
            <Text style={styles.tileTime}>{fmt(item.timestamp)}</Text>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>‹</Text>
        </TouchableOpacity>
        <View style={styles.headerInfo}>
          <Text style={styles.headerTitle}>Notifications</Text>
          {unread.length > 0 && <Text style={styles.headerSub}>{unread.length} unread</Text>}
        </View>
        {unread.length > 0 && (
          <TouchableOpacity onPress={markAllRead}>
            <Text style={styles.markAllText}>Mark all read</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={clearAll} style={styles.clearBtn}>
          <Text style={styles.clearBtnText}>⋮</Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {(['all', 'unread'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === 'all' ? `All (${items.length})` : `Unread (${unread.length})`}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filtersRow} contentContainerStyle={styles.filtersContent}>
        {FILTERS.map(f => {
          const isSelected = filter === f;
          const meta = f ? TYPE_META[f] : null;
          const color = meta?.color ?? '#3B82F6';
          const label = meta?.label ?? 'All';
          return (
            <TouchableOpacity
              key={f ?? 'all'}
              style={[styles.chip, isSelected && { backgroundColor: color + '33', borderColor: color }]}
              onPress={() => setFilter(isSelected ? null : f)}
            >
              <Text style={[styles.chipText, isSelected && { color, fontWeight: '600' }]}>{label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* List */}
      <FlatList
        data={displayed}
        keyExtractor={i => i.id}
        renderItem={renderItem}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>🔔</Text>
            <Text style={styles.emptyText}>No notifications</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0E1A' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, backgroundColor: '#0D1117' },
  backBtn: { marginRight: 12 },
  backText: { fontSize: 24, color: '#fff' },
  headerInfo: { flex: 1 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#fff' },
  headerSub: { fontSize: 12, color: '#3B82F6' },
  markAllText: { fontSize: 13, color: '#3B82F6', marginRight: 8 },
  clearBtn: { padding: 4 },
  clearBtnText: { fontSize: 20, color: 'rgba(255,255,255,0.7)' },
  tabs: { flexDirection: 'row', backgroundColor: '#0D1117', paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.08)' },
  tab: { paddingVertical: 12, marginRight: 24, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabActive: { borderBottomColor: '#3B82F6' },
  tabText: { color: 'rgba(255,255,255,0.5)', fontSize: 14 },
  tabTextActive: { color: '#3B82F6', fontWeight: '600' },
  filtersRow: { maxHeight: 48, backgroundColor: '#0D1117' },
  filtersContent: { paddingHorizontal: 16, paddingVertical: 8, gap: 8, flexDirection: 'row' },
  chip: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)', backgroundColor: '#1A2035' },
  chipText: { color: 'rgba(255,255,255,0.54)', fontSize: 12 },
  tile: { flexDirection: 'row', padding: 16, alignItems: 'flex-start' },
  iconBadge: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  iconText: { fontSize: 18 },
  tileContent: { flex: 1 },
  tileRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  tileTitle: { flex: 1, fontSize: 14, color: '#fff', fontWeight: '400' },
  tileTitleBold: { fontWeight: '600' },
  dot: { width: 8, height: 8, borderRadius: 4, marginLeft: 8 },
  tileBody: { fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 6 },
  tileFooter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  typeBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  typeBadgeText: { fontSize: 10, fontWeight: '600' },
  tileTime: { fontSize: 11, color: 'rgba(255,255,255,0.4)' },
  separator: { height: 1, backgroundColor: 'rgba(255,255,255,0.06)' },
  empty: { alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyIcon: { fontSize: 48, marginBottom: 16, opacity: 0.3 },
  emptyText: { fontSize: 16, color: 'rgba(255,255,255,0.4)' },
});
