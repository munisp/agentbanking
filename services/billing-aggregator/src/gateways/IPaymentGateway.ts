export interface PaymentInitInput {
  amount: number;
  email: string;
  reference: string;
  callback_url: string;
  metadata: Record<string, unknown>;
}

export interface PaymentInitResult {
  reference: string;
  authorization_url: string;
  access_code?: string;
  gateway: string;
  public_key?: string;
}

export interface PaymentVerifyResult {
  reference: string;
  status: "success" | "failed" | "pending";
  amount: number;
  currency: string;
  gateway_response: string;
  metadata: Record<string, unknown>;
}

export interface IPaymentGateway {
  readonly name: string;
  initialize(input: PaymentInitInput): Promise<PaymentInitResult>;
  verify(reference: string): Promise<PaymentVerifyResult>;
  validateWebhook(rawBody: string, signature: string): boolean;
}
