import crypto from "crypto";
import type { IPaymentGateway, PaymentInitInput, PaymentInitResult, PaymentVerifyResult } from "./IPaymentGateway";

const BASE = "https://api.stripe.com/v1";

export class StripeGateway implements IPaymentGateway {
  readonly name = "stripe";

  private get secretKey(): string {
    const key = process.env.STRIPE_SECRET_KEY;
    if (!key) throw new Error("STRIPE_SECRET_KEY is not set");
    return key;
  }

  private get webhookSecret(): string {
    return process.env.STRIPE_WEBHOOK_SECRET ?? "";
  }

  private async call<T>(path: string, body: Record<string, string>): Promise<T> {
    const encoded = new URLSearchParams(body).toString();
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.secretKey}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: encoded,
    });
    const data = await res.json() as any;
    if (!res.ok) throw new Error(data?.error?.message ?? `Stripe error ${res.status}`);
    return data as T;
  }

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
      headers: { Authorization: `Bearer ${this.secretKey}` },
    });
    const data = await res.json() as any;
    if (!res.ok) throw new Error(data?.error?.message ?? `Stripe error ${res.status}`);
    return data as T;
  }

  async initialize(input: PaymentInitInput): Promise<PaymentInitResult> {
    const amountInKobo = Math.round(input.amount * 100);

    const session = await this.call<any>("/checkout/sessions", {
      "payment_method_types[]": "card",
      "mode": "payment",
      "customer_email": input.email,
      "client_reference_id": input.reference,
      "success_url": `${input.callback_url}&session_id={CHECKOUT_SESSION_ID}`,
      "cancel_url": input.callback_url,
      "line_items[0][price_data][currency]": "ngn",
      "line_items[0][price_data][unit_amount]": String(amountInKobo),
      "line_items[0][price_data][product_data][name]": "54agent Credit Top-up",
      "line_items[0][quantity]": "1",
      "metadata[tenant_id]": String(input.metadata.tenant_id ?? ""),
      "metadata[reference]": input.reference,
    });

    return {
      reference: input.reference,
      authorization_url: session.url,
      access_code: session.id,
      gateway: this.name,
    };
  }

  async verify(reference: string): Promise<PaymentVerifyResult> {
    const isSessionId = reference.startsWith("cs_");
    let session: any;

    if (isSessionId) {
      session = await this.get<any>(`/checkout/sessions/${reference}`);
    } else {
      const res = await fetch(
        `${BASE}/checkout/sessions?client_reference_id=${encodeURIComponent(reference)}&limit=1`,
        { headers: { Authorization: `Bearer ${this.secretKey}` } },
      );
      const body = await res.json() as any;
      session = body.data?.[0];
      if (!session) throw new Error("Stripe session not found for reference");
    }

    const status =
      session.payment_status === "paid" ? "success" :
      session.payment_status === "unpaid" ? "pending" : "failed";

    return {
      reference: session.client_reference_id ?? reference,
      status,
      amount: (session.amount_total ?? 0) / 100,
      currency: (session.currency ?? "ngn").toUpperCase(),
      gateway_response: session.payment_status,
      metadata: session.metadata ?? {},
    };
  }

  validateWebhook(rawBody: string, signatureHeader: string): boolean {
    if (!this.webhookSecret || !signatureHeader) return false;
    const parts = Object.fromEntries(
      signatureHeader.split(",").map((p) => p.split("=")),
    );
    const timestamp = parts["t"];
    const expected = parts["v1"];
    if (!timestamp || !expected) return false;

    const signed = crypto
      .createHmac("sha256", this.webhookSecret)
      .update(`${timestamp}.${rawBody}`)
      .digest("hex");

    return crypto.timingSafeEqual(Buffer.from(signed), Buffer.from(expected));
  }
}
