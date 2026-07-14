import { TenantFeatureFlag, TenantStatus } from "../utils/enums";

export interface ICreateTenantPayload {
  name: string;
  type: string;
  tenantId: string;
  contact: {
    email: string;
    name: string;
    phone?: string;
  };
  cacCertificateUrl?: string;
  cbnLicenseUrl?: string;
  branding?: {
    logoUrl?: string;
    faviconUrl?: string;
    primaryColor?: string;
    secondaryColor?: string;
    domain?: string;
  };
  features?: ITenantFeature[];
  plan?: BillingPlan;
  apiConfiguration?: {
    webhookUrl?: string;
    callbackUrl?: string;
  };
}

export interface ITenantFeature {
  flag: TenantFeatureFlag;
  config: any;
}

export interface ITenant {
  id: number;
  tenant_id: string;
  status: TenantStatus;
  kyc_url: string;
}
