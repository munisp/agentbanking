import type { IPaymentGateway } from "./IPaymentGateway";
import { FlutterwaveGateway } from "./FlutterwaveGateway";
import { PaystackGateway } from "./PaystackGateway";
import { StripeGateway } from "./StripeGateway";

export function getPaymentGateway(): IPaymentGateway {
  switch (process.env.PAYMENT_GATEWAY?.toLowerCase()) {
    case "flutterwave": return new FlutterwaveGateway();
    case "stripe":      return new StripeGateway();
    case "paystack":
    default:            return new PaystackGateway();
  }
}

export type { IPaymentGateway, PaymentInitInput, PaymentInitResult, PaymentVerifyResult } from "./IPaymentGateway";
