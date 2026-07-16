import type { IPaymentGateway, PaymentInitInput, PaymentInitResult, PaymentVerifyResult } from "./IPaymentGateway";

const BASE = "https://api.flutterwave.com/v3";

export class FlutterwaveGateway implements IPaymentGateway {
  readonly name = "flutterwave";

  private get secretKey(): string {
    const key = process.env.FLUTTERWAVE_SECRET_KEY;
    if (!key) throw new Error("FLUTTERWAVE_SECRET_KEY is not set");
    return key;
  }

  private get publicKey(): string {
    return process.env.FLUTTERWAVE_PUBLIC_KEY ?? "";
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
    if (!res.ok || body.status === "error") {
      throw new Error(body.message ?? `Flutterwave error ${res.status}`);
    }
    return body.data as T;
  }

  async initialize(input: PaymentInitInput): Promise<PaymentInitResult> {
    const data = await this.call<any>("/payments", {
      method: "POST",
      body: JSON.stringify({
        tx_ref: input.reference,
        amount: input.amount,
        currency: "NGN",
        redirect_url: input.callback_url,
        customer: { email: input.email },
        meta: input.metadata,
        customizations: { title: "54agent Credit Top-up" },
      }),
    });

    return {
      reference: input.reference,
      authorization_url: data.link,
      gateway: this.name,
      public_key: this.publicKey,
    };
  }

  async verify(reference: string): Promise<PaymentVerifyResult> {
    const res = await fetch(`${BASE}/transactions?tx_ref=${encodeURIComponent(reference)}`, {
      headers: { Authorization: `Bearer ${this.secretKey}` },
    });
    const body = await res.json() as any;
    const tx = (body.data as any[])?.[0];
    if (!tx) throw new Error("Transaction not found");

    return {
      reference: tx.tx_ref,
      status: tx.status === "successful" ? "success" : tx.status === "failed" ? "failed" : "pending",
      amount: tx.amount,
      currency: tx.currency,
      gateway_response: tx.processor_response ?? tx.status,
      metadata: tx.meta ?? {},
    };
  }

  validateWebhook(_rawBody: string, signature: string): boolean {
    const hash = process.env.FLUTTERWAVE_HASH ?? "";
    return hash.length > 0 && signature === hash;
  }
}
