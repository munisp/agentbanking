import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert, Switch,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

interface Card {
  id: string;
  last4: string;
  brand: string;
  type: string;
  status: string;
  expiryMonth: number;
  expiryYear: number;
  cardholderName: string;
  spendingLimit: number;
  spent: number;
  isLocked: boolean;
}

const CardsScreen: React.FC = () => {
  const navigation = useNavigation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cards, setCards] = useState<Card[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadCards = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/cards');
      const items = Array.isArray(response) ? response :
        (response as any)?.items ?? (response as any)?.cards ?? [];
      setCards(items.map((c: any) => ({
        id: c.id ?? String(Math.random()),
        last4: c.last4 ?? c.lastFour ?? '****',
        brand: c.brand ?? c.network ?? 'Visa',
        type: c.type ?? 'virtual',
        status: c.status ?? 'active',
        expiryMonth: c.expiryMonth ?? c.expiry_month ?? 12,
        expiryYear: c.expiryYear ?? c.expiry_year ?? 2026,
        cardholderName: c.cardholderName ?? c.cardholder_name ?? '',
        spendingLimit: c.spendingLimit ?? c.spending_limit ?? 500000,
        spent: c.spent ?? c.totalSpent ?? 0,
        isLocked: c.isLocked ?? c.is_locked ?? false,
      })));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadCards(); }, [loadCards]);

  const toggleLock = async (card: Card) => {
    try {
      await apiClient.post('/cards/toggle-lock', { cardId: card.id, lock: !card.isLocked });
      setCards(prev => prev.map(c => c.id === card.id ? { ...c, isLocked: !c.isLocked } : c));
    } catch (e) {
      Alert.alert('Error', 'Failed to update card');
    }
  };

  const freezeCard = (card: Card) => {
    Alert.alert('Freeze Card', `Freeze card ending in ${card.last4}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Freeze', style: 'destructive',
        onPress: async () => {
          try {
            await apiClient.post('/cards/freeze', { cardId: card.id });
            setCards(prev => prev.map(c => c.id === card.id ? { ...c, status: 'frozen' } : c));
          } catch (e) {
            Alert.alert('Error', 'Failed to freeze card');
          }
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading Cards...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Failed to load cards</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadCards()}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const renderCard = ({ item }: { item: Card }) => {
    const spendPercent = item.spendingLimit > 0 ? Math.min(100, (item.spent / item.spendingLimit) * 100) : 0;
    return (
      <View style={[styles.card, item.status === 'frozen' && styles.frozenCard]}>
        <View style={styles.cardHeader}>
          <Text style={styles.brand}>{item.brand.toUpperCase()}</Text>
          <Text style={[styles.statusBadge, item.status === 'active' ? styles.activeBadge : styles.frozenBadge]}>
            {item.status.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.cardNumber}>**** **** **** {item.last4}</Text>
        <Text style={styles.cardName}>{item.cardholderName}</Text>
        <Text style={styles.expiry}>Exp: {String(item.expiryMonth).padStart(2, '0')}/{item.expiryYear}</Text>
        <View style={styles.spendingBar}>
          <View style={[styles.spendingFill, { width: `${spendPercent}%` }]} />
        </View>
        <Text style={styles.spendingText}>
          Spent: NGN {item.spent.toLocaleString()} / {item.spendingLimit.toLocaleString()}
        </Text>
        <View style={styles.cardActions}>
          <View style={styles.lockRow}>
            <Text style={styles.lockLabel}>{item.isLocked ? 'Locked' : 'Active'}</Text>
            <Switch value={item.isLocked} onValueChange={() => toggleLock(item)} />
          </View>
          {item.status === 'active' && (
            <TouchableOpacity onPress={() => freezeCard(item)}>
              <Text style={styles.freezeText}>Freeze</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>My Cards</Text>
        <Text style={styles.subtitle}>{cards.length} card{cards.length !== 1 ? 's' : ''}</Text>
      </View>
      <FlatList
        data={cards}
        keyExtractor={item => item.id}
        renderItem={renderCard}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadCards(true)} />}
        ListEmptyComponent={<Text style={styles.empty}>No cards. Request a virtual card to get started.</Text>}
        contentContainerStyle={styles.list}
      />
      <TouchableOpacity style={styles.fab} onPress={() => (navigation as any).navigate('RequestCard')}>
        <Text style={styles.fabText}>+ New Card</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#666' },
  errorText: { fontSize: 16, color: '#D32F2F', marginBottom: 16 },
  retryBtn: { backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  retryBtnText: { color: '#FFF', fontWeight: '600' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  list: { padding: 16, paddingBottom: 80 },
  card: { backgroundColor: '#1A1A2E', borderRadius: 16, padding: 20, marginBottom: 16 },
  frozenCard: { opacity: 0.6 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  brand: { color: '#FFD700', fontSize: 18, fontWeight: 'bold' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, fontSize: 11, fontWeight: '600' },
  activeBadge: { backgroundColor: '#4CAF50', color: '#FFF' },
  frozenBadge: { backgroundColor: '#FF5722', color: '#FFF' },
  cardNumber: { color: '#FFF', fontSize: 20, fontWeight: '600', letterSpacing: 2, marginBottom: 8 },
  cardName: { color: '#CCC', fontSize: 14 },
  expiry: { color: '#AAA', fontSize: 13, marginTop: 4 },
  spendingBar: { height: 4, backgroundColor: '#333', borderRadius: 2, marginTop: 12 },
  spendingFill: { height: 4, backgroundColor: '#4CAF50', borderRadius: 2 },
  spendingText: { color: '#999', fontSize: 12, marginTop: 4 },
  cardActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  lockRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  lockLabel: { color: '#CCC', fontSize: 14 },
  freezeText: { color: '#FF5722', fontSize: 14, fontWeight: '600' },
  empty: { textAlign: 'center', color: '#999', fontSize: 16, marginTop: 40 },
  fab: { position: 'absolute', bottom: 24, right: 24, backgroundColor: '#007AFF', paddingHorizontal: 20, paddingVertical: 14, borderRadius: 28, elevation: 4 },
  fabText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
});

export default CardsScreen;
