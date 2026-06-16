// React Native Wallet Service
import { APIClient } from '../api/APIClient';

export interface WalletBalance {
  currency: string;
  balance: number;
  symbol: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  phone: string;
  country: string;
  kycStatus: 'pending' | 'verified' | 'rejected';
}

export class WalletService {
  private static apiClient = new APIClient();

  static async getWallets(): Promise<WalletBalance[]> {
    const response = await this.apiClient.get('/wallet/balances');
    return response.data;
  }

  static async getUserProfile(): Promise<UserProfile> {
    const response = await this.apiClient.get('/user/profile');
    return response.data;
  }

  static async updateUserProfile(updates: Partial<UserProfile>): Promise<UserProfile> {
    const response = await this.apiClient.put('/user/profile', updates);
    return response.data;
  }

  static async getExchangeRate(from: string, to: string): Promise<any> {
    const response = await this.apiClient.get(`/wallet/exchange-rate?from=${from}&to=${to}`);
    return response.data;
  }

  static async exchangeCurrency(from: string, to: string, amount: number): Promise<any> {
    const response = await this.apiClient.post('/wallet/exchange', { from, to, amount });
    return response.data;
  }
}
