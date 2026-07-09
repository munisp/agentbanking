import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  Alert,
  RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface Beneficiary {
  id: string;
  name: string;
  accountNumber: string;
  bankCode: string;
  bankName: string;
  nickname?: string;
  lastUsed?: string;
  transferCount: number;
}

const BeneficiariesScreen: React.FC = () => {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/beneficiaries');
      const items = Array.isArray(response) ? response :
        (response as any)?.items ?? (response as any)?.beneficiaries ?? [];
      setBeneficiaries(items.map((b: any) => ({
        id: b.id ?? String(Math.random()),
        name: b.name ?? b.accountName ?? 'Unknown',
        accountNumber: b.accountNumber ?? b.account_number ?? '',
        bankCode: b.bankCode ?? b.bank_code ?? '',
        bankName: b.bankName ?? b.bank_name ?? 'Unknown Bank',
        nickname: b.nickname,
        lastUsed: b.lastUsed ?? b.last_used,
        transferCount: b.transferCount ?? b.transfer_count ?? 0,
      })));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDelete = (id: string, name: string) => {
    Alert.alert('Remove Beneficiary', `Remove ${name} from your beneficiaries?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove', style: 'destructive',
        onPress: async () => {
          try {
            await apiClient.post('/beneficiaries/delete', { id });
            setBeneficiaries(prev => prev.filter(b => b.id !== id));
          } catch (e) {
            Alert.alert('Error', 'Failed to remove beneficiary');
          }
        },
      },
    ]);
  };

  const handleSendMoney = (beneficiary: Beneficiary) => {
    (navigation as any).navigate('SendMoney', {
      beneficiaryId: beneficiary.id,
      accountNumber: beneficiary.accountNumber,
      bankCode: beneficiary.bankCode,
      name: beneficiary.name,
    });
  };

  const filtered = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    b.accountNumber.includes(search) ||
    b.bankName.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading Beneficiaries...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>Failed to load beneficiaries</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadData()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const renderItem = ({ item }: { item: Beneficiary }) => (
    <View style={styles.card}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{item.name.charAt(0).toUpperCase()}</Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.name}>{item.nickname ?? item.name}</Text>
        <Text style={styles.account}>{item.bankName} • {item.accountNumber}</Text>
        {item.lastUsed && <Text style={styles.meta}>Last used: {new Date(item.lastUsed).toLocaleDateString()}</Text>}
        <Text style={styles.meta}>{item.transferCount} transfers</Text>
      </View>
      <View style={styles.actions}>
        <TouchableOpacity style={styles.sendBtn} onPress={() => handleSendMoney(item)}>
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => handleDelete(item.id, item.name)}>
          <Text style={styles.deleteText}>Remove</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Beneficiaries</Text>
        <Text style={styles.subtitle}>{beneficiaries.length} saved</Text>
      </View>
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name, account, or bank..."
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
        />
      </View>
      <FlatList
        data={filtered}
        keyExtractor={item => item.id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadData(true)} />}
        ListEmptyComponent={
          <Text style={styles.emptyText}>
            {search ? 'No matching beneficiaries' : 'No beneficiaries yet. Add one to get started.'}
          </Text>
        }
        contentContainerStyle={styles.listContent}
      />
      <TouchableOpacity style={styles.fab} onPress={() => (navigation as any).navigate('AddBeneficiary')}>
        <Text style={styles.fabText}>+ Add</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  errorText: { fontSize: 16, color: '#D32F2F', marginBottom: 16 },
  retryBtn: { backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  retryText: { color: '#FFF', fontWeight: '600' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  searchContainer: { padding: 16, backgroundColor: '#FFF' },
  searchInput: { backgroundColor: '#F0F0F0', borderRadius: 8, padding: 12, fontSize: 16 },
  listContent: { paddingBottom: 80 },
  card: { flexDirection: 'row', backgroundColor: '#FFF', padding: 16, marginHorizontal: 16, marginTop: 8, borderRadius: 12, alignItems: 'center' },
  avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#007AFF', justifyContent: 'center', alignItems: 'center' },
  avatarText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  info: { flex: 1, marginLeft: 12 },
  name: { fontSize: 16, fontWeight: '600', color: '#333' },
  account: { fontSize: 13, color: '#666', marginTop: 2 },
  meta: { fontSize: 12, color: '#999', marginTop: 2 },
  actions: { alignItems: 'center', gap: 8 },
  sendBtn: { backgroundColor: '#007AFF', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 6 },
  sendText: { color: '#FFF', fontWeight: '600', fontSize: 13 },
  deleteText: { color: '#D32F2F', fontSize: 12, marginTop: 8 },
  emptyText: { textAlign: 'center', color: '#999', fontSize: 16, marginTop: 40, paddingHorizontal: 32 },
  fab: { position: 'absolute', bottom: 24, right: 24, backgroundColor: '#007AFF', paddingHorizontal: 20, paddingVertical: 14, borderRadius: 28, elevation: 4 },
  fabText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
});

export default BeneficiariesScreen;
