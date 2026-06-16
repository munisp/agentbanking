// React Native API Service - All 6 Payment Systems
import { APIClient } from './APIClient';

export interface Beneficiary {
  id: string;
  name: string;
  accountNumber: string;
  bankName: string;
  bankCode: string;
  country: string;
  currency: string;
  paymentSystem: string;
}

export class BeneficiaryService {
  private static apiClient = new APIClient();

  // NIBSS - Nigeria Inter-Bank Settlement System
  static async nibssTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/nibss/transfer', request);
  }

  static async verifyNIBSSAccount(accountNumber: string, bankCode: string): Promise<any> {
    return await this.apiClient.post('/payments/nibss/verify', { accountNumber, bankCode });
  }

  // PAPSS - Pan-African Payment System
  static async papssTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/papss/transfer', request);
  }

  static async getPAPSSExchangeRate(from: string, to: string): Promise<any> {
    return await this.apiClient.get(`/payments/papss/exchange-rate?from=${from}&to=${to}`);
  }

  // PIX - Brazil Instant Payment
  static async pixTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/pix/transfer', request);
  }

  static async generatePIXQRCode(amount: number, description: string): Promise<any> {
    return await this.apiClient.post('/payments/pix/generate-qr', { amount, description });
  }

  static async decodePIXQRCode(qrCode: string): Promise<any> {
    return await this.apiClient.post('/payments/pix/decode-qr', { qrCode });
  }

  // UPI - Unified Payments Interface (India)
  static async upiTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/upi/transfer', request);
  }

  static async verifyUPIVPA(vpa: string): Promise<any> {
    return await this.apiClient.post('/payments/upi/verify-vpa', { vpa });
  }

  // Mojaloop - Open-source Payment Platform
  static async mojaloopTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/mojaloop/transfer', request);
  }

  static async mojaloopPartyLookup(partyId: string, partyIdType: string): Promise<any> {
    return await this.apiClient.get(`/payments/mojaloop/parties/${partyIdType}/${partyId}`);
  }

  // CIPS - China International Payment System
  static async cipsTransfer(request: any): Promise<any> {
    return await this.apiClient.post('/payments/cips/transfer', request);
  }

  static async verifyCIPSBeneficiary(swiftCode: string, accountNumber: string): Promise<any> {
    return await this.apiClient.post('/payments/cips/verify', { swiftCode, accountNumber });
  }

  // Beneficiary Management
  static async getBeneficiaries(): Promise<Beneficiary[]> {
    const response = await this.apiClient.get('/beneficiaries');
    return response.data;
  }

  static async addBeneficiary(beneficiary: Omit<Beneficiary, 'id'>): Promise<Beneficiary> {
    const response = await this.apiClient.post('/beneficiaries', beneficiary);
    return response.data;
  }

  static async deleteBeneficiary(id: string): Promise<void> {
    await this.apiClient.delete(`/beneficiaries/${id}`);
  }
}
