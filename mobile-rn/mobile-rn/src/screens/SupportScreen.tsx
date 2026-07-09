import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput, Alert,
} from 'react-native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface Ticket {
  id: string;
  subject: string;
  status: string;
  priority: string;
  lastReply: string;
  createdAt: string;
}

const SupportScreen: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [newSubject, setNewSubject] = useState('');
  const [newMessage, setNewMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadTickets = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const response = await apiClient.get('/support/tickets');
      const items = Array.isArray(response) ? response :
        (response as any)?.items ?? (response as any)?.tickets ?? [];
      setTickets(items.map((t: any) => ({
        id: t.id ?? String(Math.random()),
        subject: t.subject ?? 'Support Request',
        status: t.status ?? 'open',
        priority: t.priority ?? 'normal',
        lastReply: t.lastReply ?? t.last_reply ?? '',
        createdAt: t.createdAt ?? t.created_at ?? new Date().toISOString(),
      })));
    } catch (e) {
      console.error('Failed to load tickets:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadTickets(); }, [loadTickets]);

  const submitTicket = async () => {
    if (!newSubject.trim() || !newMessage.trim()) {
      Alert.alert('Error', 'Please fill in both subject and message');
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post('/support/tickets', { subject: newSubject, message: newMessage });
      Alert.alert('Success', 'Ticket created successfully');
      setNewSubject('');
      setNewMessage('');
      setShowNew(false);
      loadTickets();
    } catch (e) {
      Alert.alert('Error', 'Failed to create ticket');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return '#FF9800';
      case 'in_progress': return '#007AFF';
      case 'resolved': return '#4CAF50';
      case 'closed': return '#999';
      default: return '#666';
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading support tickets...</Text>
      </View>
    );
  }

  const renderTicket = ({ item }: { item: Ticket }) => (
    <View style={styles.ticketCard}>
      <View style={styles.ticketHeader}>
        <Text style={styles.ticketSubject}>{item.subject}</Text>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
          <Text style={styles.statusText}>{item.status.replace('_', ' ')}</Text>
        </View>
      </View>
      {item.lastReply && <Text style={styles.lastReply} numberOfLines={2}>{item.lastReply}</Text>}
      <Text style={styles.ticketDate}>{new Date(item.createdAt).toLocaleDateString()}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Support</Text>
        <Text style={styles.subtitle}>{tickets.length} ticket{tickets.length !== 1 ? 's' : ''}</Text>
      </View>

      {showNew && (
        <View style={styles.newTicket}>
          <TextInput style={styles.input} placeholder="Subject" value={newSubject} onChangeText={setNewSubject} />
          <TextInput
            style={[styles.input, styles.messageInput]}
            placeholder="Describe your issue..."
            value={newMessage}
            onChangeText={setNewMessage}
            multiline
            numberOfLines={4}
          />
          <View style={styles.newActions}>
            <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowNew(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.submitBtn} onPress={submitTicket} disabled={submitting}>
              <Text style={styles.submitText}>{submitting ? 'Submitting...' : 'Submit'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      <FlatList
        data={tickets}
        keyExtractor={item => item.id}
        renderItem={renderTicket}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadTickets(true)} />}
        ListEmptyComponent={<Text style={styles.empty}>No support tickets</Text>}
        contentContainerStyle={styles.list}
      />

      {!showNew && (
        <TouchableOpacity style={styles.fab} onPress={() => setShowNew(true)}>
          <Text style={styles.fabText}>+ New Ticket</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  newTicket: { backgroundColor: '#FFF', margin: 16, borderRadius: 12, padding: 16 },
  input: { backgroundColor: '#F0F0F0', borderRadius: 8, padding: 12, fontSize: 16, marginBottom: 12 },
  messageInput: { height: 100, textAlignVertical: 'top' },
  newActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 12 },
  cancelBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8 },
  cancelText: { color: '#666', fontSize: 15 },
  submitBtn: { backgroundColor: '#007AFF', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8 },
  submitText: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  list: { padding: 16, paddingBottom: 80 },
  ticketCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, marginBottom: 8 },
  ticketHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ticketSubject: { fontSize: 16, fontWeight: '600', color: '#333', flex: 1, marginRight: 8 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  statusText: { color: '#FFF', fontSize: 11, fontWeight: '600', textTransform: 'uppercase' },
  lastReply: { fontSize: 14, color: '#666', marginTop: 8 },
  ticketDate: { fontSize: 12, color: '#999', marginTop: 8 },
  empty: { textAlign: 'center', color: '#999', fontSize: 16, marginTop: 40 },
  fab: { position: 'absolute', bottom: 24, right: 24, backgroundColor: '#007AFF', paddingHorizontal: 20, paddingVertical: 14, borderRadius: 28, elevation: 4 },
  fabText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
});

export default SupportScreen;
