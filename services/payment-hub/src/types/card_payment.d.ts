export interface EMVStandardResponse {
  merchantName: string;
  merchantAddress: string;
  processingCode: string;
  merchantID: string;
  cardExpiry: string;
  amount: number;
  terminalID: string;
  maskedPAN: string;
  stan: string;
  responseCode: string;
  responseMessage: string;
  rrn: string;
}
