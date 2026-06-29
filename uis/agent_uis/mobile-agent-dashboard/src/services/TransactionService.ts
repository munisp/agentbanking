// React Native Transaction Service
import { APIClient } from '../api/APIClient';

export interface Transaction {
  id: string;
  type: 'debit' | 'credit';
  amount: number;
  currency: string;
  status: 'completed' | 'pending' | 'failed';
  date: string;
  recipient?: string;
  sender?: string;
  paymentSystem: string;
  reference: string;
}

export class TransactionService {
  private static apiClient = new APIClient();

  static async getAllTransactions(): Promise<Transaction[]> {
    const response = await this.apiClient.get('/transactions');
    return response.data;
  }

  static async getRecentTransactions(limit: number = 5): Promise<Transaction[]> {
    const response = await this.apiClient.get(`/transactions/recent?limit=${limit}`);
    return response.data;
  }

  static async getTransactionById(id: string): Promise<any> {
    const response = await this.apiClient.get(`/transactions/${id}`);
    return response.data;
  }

  static async exportTransactions(format: 'csv' | 'pdf' = 'csv'): Promise<void> {
    await this.apiClient.get(`/transactions/export?format=${format}`);
  }
}
