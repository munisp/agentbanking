import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, TextInput } from 'react-native';
import { TransactionService, Transaction } from '../services/TransactionService';
import { AnalyticsService } from '../services/AnalyticsService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


export const TransactionsScreen = ({ navigation }: any) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [filteredTransactions, setFilteredTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    AnalyticsService.trackScreenView('Transactions');
    loadTransactions();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [filter, searchQuery, transactions]);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await TransactionService.getAllTransactions();
      setTransactions(data);
    } catch (error) {
      AnalyticsService.trackError('transactions_load_failed', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = transactions;

    // Apply type filter
    if (filter !== 'all') {
      filtered = filtered.filter(tx => tx.type === filter);
    }

    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(tx =>
        tx.recipient?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tx.sender?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tx.reference.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredTransactions(filtered);
  };

  const handleExport = async () => {
    try {
      await TransactionService.exportTransactions('csv');
      AnalyticsService.trackButtonClick('export_transactions');
    } catch (error) {
      AnalyticsService.trackError('export_failed', error);
    }
  };

  const renderTransaction = ({ item }: { item: Transaction }) => (
    <TouchableOpacity
      style={styles.transactionCard}
      onPress={() => navigation.navigate('TransactionDetail', { transaction: item })}
    >
      <View style={styles.transactionIcon}>
        <Text style={styles.iconText}>{item.type === 'debit' ? '↑' : '↓'}</Text>
      </View>
      
      <View style={styles.transactionDetails}>
        <Text style={styles.transactionRecipient}>
          {item.recipient || item.sender || item.type}
        </Text>
        <Text style={styles.transactionDate}>{item.date}</Text>
        <Text style={styles.transactionSystem}>{item.paymentSystem}</Text>
      </View>

      <View style={styles.transactionAmount}>
        <Text style={[styles.amount, item.type === 'debit' ? styles.amountDebit : styles.amountCredit]}>
          {item.type === 'debit' ? '-' : '+'}{item.currency} {item.amount}
        </Text>
        <View style={[styles.statusBadge, styles[`status${item.status.charAt(0).toUpperCase() + item.status.slice(1)}`]]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Transactions</Text>
        <TouchableOpacity style={styles.exportBtn} onPress={handleExport}>
          <Text style={styles.exportBtnText}>Export</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.controls}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search transactions..."
          value={searchQuery}
          onChangeText={setSearchQuery}
        />

        <View style={styles.filterButtons}>
          {['all', 'debit', 'credit'].map((f) => (
            <TouchableOpacity
              key={f}
              style={[styles.filterBtn, filter === f && styles.filterBtnActive]}
              onPress={() => setFilter(f)}
            >
              <Text style={[styles.filterBtnText, filter === f && styles.filterBtnTextActive]}>
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <Text>Loading transactions...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredTransactions}
          renderItem={renderTransaction}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContainer}
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Text style={styles.emptyStateText}>No transactions found</Text>
            </View>
          }
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#FFFFFF',
  },
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  exportBtn: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  exportBtnText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  controls: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    marginBottom: 8,
  },
  searchInput: {
    borderWidth: 1,
    borderColor: '#E5E5EA',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  filterButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  filterBtn: {
    flex: 1,
    padding: 12,
    backgroundColor: '#F2F2F7',
    borderRadius: 8,
    alignItems: 'center',
  },
  filterBtnActive: {
    backgroundColor: '#007AFF',
  },
  filterBtnText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#1C1C1E',
  },
  filterBtnTextActive: {
    color: '#FFFFFF',
  },
  listContainer: {
    padding: 16,
  },
  transactionCard: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginBottom: 12,
  },
  transactionIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F2F2F7',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconText: {
    fontSize: 20,
  },
  transactionDetails: {
    flex: 1,
  },
  transactionRecipient: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  transactionDate: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 2,
  },
  transactionSystem: {
    fontSize: 12,
    color: '#8E8E93',
  },
  transactionAmount: {
    alignItems: 'flex-end',
  },
  amount: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  amountDebit: {
    color: '#FF3B30',
  },
  amountCredit: {
    color: '#34C759',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusCompleted: {
    backgroundColor: 'rgba(52, 199, 89, 0.1)',
  },
  statusPending: {
    backgroundColor: 'rgba(255, 149, 0, 0.1)',
  },
  statusFailed: {
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
  },
  statusText: {
    fontSize: 10,
    fontWeight: '500',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyStateText: {
    fontSize: 16,
    color: '#8E8E93',
  },
});
