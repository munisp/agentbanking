export interface BillingPlan {
  name: string;
  price: number;
  features: string[];
}

export interface IGetBillingInfoResponse {
  plan: BillingPlan;
  billingCycle: "monthly" | "yearly";
  nextBillingDate: string;
  status: "active" | "past_due" | "canceled";
}

export interface IBillingProfile {
  tenantId: string;
  billingInfo: IGetBillingInfoResponse;
}