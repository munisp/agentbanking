import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Share } from 'react-native';
import { AnalyticsService } from '../services/AnalyticsService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


export const TransactionDetailScreen = ({ route }: any) => {
  const { transaction } = route.params;

  React.useEffect(() => {
    AnalyticsService.trackScreenView('TransactionDetail');
  }, []);

  const handleShare = async () => {
    try {
      await Share.share({
        message: `Transaction Receipt\nAmount: ${transaction.currency} ${transaction.amount}\nRecipient: ${transaction.recipient}\nReference: ${transaction.reference}`,
      });
      AnalyticsService.trackButtonClick('transaction_shared');
    } catch (error) {
      console.error(error);
    }
  };

  const handleDownloadReceipt = () => {
    AnalyticsService.trackButtonClick('receipt_downloaded');
    // Download receipt logic
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.statusSection}>
        <View style={[styles.statusBadge, styles[`status${transaction.status.charAt(0).toUpperCase()}${transaction.status.slice(1)}`]]}>
          <Text style={styles.statusText}>{transaction.status.toUpperCase()}</Text>
        </View>
        <Text style={styles.amount}>{transaction.currency} {transaction.amount}</Text>
        <Text style={styles.date}>{transaction.date}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Transaction Details</Text>
        
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Reference Number</Text>
          <Text style={styles.detailValue}>{transaction.reference}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Type</Text>
          <Text style={styles.detailValue}>{transaction.type}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Payment System</Text>
          <Text style={styles.detailValue}>{transaction.paymentSystem}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Status</Text>
          <Text style={[styles.detailValue, styles[`status${transaction.status.charAt(0).toUpperCase()}${transaction.status.slice(1)}`]]}>
            {transaction.status}
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recipient Information</Text>
        
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Name</Text>
          <Text style={styles.detailValue}>{transaction.recipient || 'N/A'}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Account Number</Text>
          <Text style={styles.detailValue}>{transaction.accountNumber || 'N/A'}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Bank</Text>
          <Text style={styles.detailValue}>{transaction.bank || 'N/A'}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Amount Breakdown</Text>
        
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Transfer Amount</Text>
          <Text style={styles.detailValue}>{transaction.currency} {transaction.amount}</Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Fee</Text>
          <Text style={styles.detailValue}>{transaction.currency} {transaction.fee || 0}</Text>
        </View>

        <View style={[styles.detailRow, styles.totalRow]}>
          <Text style={styles.totalLabel}>Total</Text>
          <Text style={styles.totalValue}>
            {transaction.currency} {(parseFloat(transaction.amount) + (transaction.fee || 0)).toFixed(2)}
          </Text>
        </View>
      </View>

      <View style={styles.actionButtons}>
        <TouchableOpacity style={styles.actionButton} onPress={handleShare}>
          <Text style={styles.actionButtonText}>Share Receipt</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.actionButton} onPress={handleDownloadReceipt}>
          <Text style={styles.actionButtonText}>Download Receipt</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.supportButton}>
        <Text style={styles.supportButtonText}>Report an Issue</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  statusSection: {
    backgroundColor: '#FFFFFF',
    padding: 32,
    alignItems: 'center',
  },
  statusBadge: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 16,
    marginBottom: 16,
  },
  statusCompleted: {
    backgroundColor: 'rgba(52, 199, 89, 0.1)',
    color: '#34C759',
  },
  statusPending: {
    backgroundColor: 'rgba(255, 149, 0, 0.1)',
    color: '#FF9500',
  },
  statusFailed: {
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
    color: '#FF3B30',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  amount: {
    fontSize: 36,
    fontWeight: '700',
    marginBottom: 8,
  },
  date: {
    fontSize: 14,
    color: '#8E8E93',
  },
  section: {
    backgroundColor: '#FFFFFF',
    marginTop: 16,
    padding: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F2F2F7',
  },
  detailLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '500',
    textAlign: 'right',
  },
  totalRow: {
    borderBottomWidth: 0,
    paddingTop: 16,
  },
  totalLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  totalValue: {
    fontSize: 16,
    fontWeight: '700',
  },
  actionButtons: {
    flexDirection: 'row',
    padding: 20,
    gap: 12,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  supportButton: {
    margin: 20,
    marginTop: 0,
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    alignItems: 'center',
  },
  supportButtonText: {
    color: '#FF3B30',
    fontSize: 14,
    fontWeight: '600',
  },
});
