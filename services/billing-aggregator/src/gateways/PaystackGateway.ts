import crypto from "crypto";
import type { IPaymentGateway, PaymentInitInput, PaymentInitResult, PaymentVerifyResult } from "./IPaymentGateway";

const BASE = "https://api.paystack.co";

export class PaystackGateway implements IPaymentGateway {
  readonly name = "paystack";

  private get secretKey(): string {
    const key = process.env.PAYSTACK_SECRET_KEY;
    if (!key) throw new Error("PAYSTACK_SECRET_KEY is not set");
    return key;
  }

  private get publicKey(): string {
    return process.env.PAYSTACK_PUBLIC_KEY ?? "";
  }

  private async call<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.secretKey}`,
        "Content-Type": "application/json",
        ...(options.headers as Record<string, string> | undefined),
      },
    });
    const body = await res.json() as any;
    if (!res.ok || !body.status) {
      throw new Error(body.message ?? `Paystack error ${res.status}`);
    }
    return body.data as T;
  }

  async initialize(input: PaymentInitInput): Promise<PaymentInitResult> {
    const data = await this.call<any>("/transaction/initialize", {
      method: "POST",
      body: JSON.stringify({
        email: input.email,
        amount: Math.round(input.amount * 100),
        reference: input.reference,
        callback_url: input.callback_url,
        metadata: input.metadata,
      }),
    });

    return {
      reference: data.reference,
      authorization_url: data.authorization_url,
      access_code: data.access_code,
      gateway: this.name,
      public_key: this.publicKey,
    };
  }

  async verify(reference: string): Promise<PaymentVerifyResult> {
    const data = await this.call<any>(`/transaction/verify/${encodeURIComponent(reference)}`);
    return {
      reference: data.reference,
      status: data.status === "success" ? "success" : data.status === "failed" ? "failed" : "pending",
      amount: data.amount / 100,
      currency: data.currency,
      gateway_response: data.gateway_response ?? data.status,
      metadata: data.metadata ?? {},
    };
  }

  validateWebhook(rawBody: string, signature: string): boolean {
    const hash = crypto
      .createHmac("sha512", this.secretKey)
      .update(rawBody)
      .digest("hex");
    return hash === signature;
  }
}
