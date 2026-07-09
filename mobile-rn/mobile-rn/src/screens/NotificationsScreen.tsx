import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface Notification {
  id: string;
  title: string;
  body: string;
  type: string;
  read: boolean;
  createdAt: string;
}

const NotificationsScreen: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const loadNotifications = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const response = await apiClient.get('/notifications');
      const items = Array.isArray(response) ? response :
        (response as any)?.items ?? (response as any)?.notifications ?? [];
      setNotifications(items.map((n: any) => ({
        id: n.id ?? String(Math.random()),
        title: n.title ?? 'Notification',
        body: n.body ?? n.message ?? '',
        type: n.type ?? 'info',
        read: n.read ?? n.isRead ?? false,
        createdAt: n.createdAt ?? n.created_at ?? new Date().toISOString(),
      })));
    } catch (e) {
      console.error('Failed to load notifications:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadNotifications(); }, [loadNotifications]);

  const markRead = async (id: string) => {
    try {
      await apiClient.post('/notifications/read', { id });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
    } catch (e) { /* best-effort */ }
  };

  const markAllRead = async () => {
    try {
      await apiClient.post('/notifications/read-all', {});
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (e) { /* best-effort */ }
  };

  const filtered = filter === 'unread' ? notifications.filter(n => !n.read) : notifications;
  const unreadCount = notifications.filter(n => !n.read).length;

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'transaction': return '#4CAF50';
      case 'security': return '#D32F2F';
      case 'promotion': return '#FF9800';
      default: return '#007AFF';
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading notifications...</Text>
      </View>
    );
  }

  const renderItem = ({ item }: { item: Notification }) => (
    <TouchableOpacity
      style={[styles.notifCard, !item.read && styles.unreadCard]}
      onPress={() => markRead(item.id)}
    >
      <View style={[styles.typeDot, { backgroundColor: getTypeColor(item.type) }]} />
      <View style={styles.notifContent}>
        <Text style={[styles.notifTitle, !item.read && styles.unreadTitle]}>{item.title}</Text>
        <Text style={styles.notifBody} numberOfLines={2}>{item.body}</Text>
        <Text style={styles.notifTime}>{new Date(item.createdAt).toLocaleDateString()}</Text>
      </View>
      {!item.read && <View style={styles.unreadDot} />}
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.title}>Notifications</Text>
          {unreadCount > 0 && (
            <TouchableOpacity onPress={markAllRead}>
              <Text style={styles.markAllText}>Mark all read</Text>
            </TouchableOpacity>
          )}
        </View>
        <View style={styles.filterRow}>
          {(['all', 'unread'] as const).map(f => (
            <TouchableOpacity
              key={f}
              style={[styles.filterBtn, filter === f && styles.filterBtnActive]}
              onPress={() => setFilter(f)}
            >
              <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
                {f === 'all' ? `All (${notifications.length})` : `Unread (${unreadCount})`}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
      <FlatList
        data={filtered}
        keyExtractor={item => item.id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadNotifications(true)} />}
        ListEmptyComponent={<Text style={styles.empty}>No notifications</Text>}
        contentContainerStyle={styles.list}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  markAllText: { color: '#007AFF', fontSize: 14, fontWeight: '600' },
  filterRow: { flexDirection: 'row', marginTop: 12, gap: 8 },
  filterBtn: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 16, backgroundColor: '#F0F0F0' },
  filterBtnActive: { backgroundColor: '#007AFF' },
  filterText: { fontSize: 13, color: '#666' },
  filterTextActive: { color: '#FFF', fontWeight: '600' },
  list: { padding: 16 },
  notifCard: { flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 12, padding: 16, marginBottom: 8, alignItems: 'center' },
  unreadCard: { backgroundColor: '#F0F7FF' },
  typeDot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
  notifContent: { flex: 1 },
  notifTitle: { fontSize: 15, fontWeight: '500', color: '#333' },
  unreadTitle: { fontWeight: '700' },
  notifBody: { fontSize: 13, color: '#666', marginTop: 4 },
  notifTime: { fontSize: 11, color: '#999', marginTop: 4 },
  unreadDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#007AFF', marginLeft: 8 },
  empty: { textAlign: 'center', color: '#999', fontSize: 16, marginTop: 40 },
});

export default NotificationsScreen;
