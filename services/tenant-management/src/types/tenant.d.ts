import { FeatureFlag, TenantType } from "../utils/enums";

export interface ICreateTenantPayload {
  name: string;
  type: TenantType;
  tenantId: string;
  cacCertificateUrl?: string;
  cbnLicenseUrl?: string;
  contact: {
    email: string;
    name: string;
    phone?: string;
  };
  branding?: {
    logoUrl?: string;
    faviconUrl?: string;
    primaryColor?: string;
    secondaryColor?: string;
    domain?: string;
  };
  features: ITenantFeature[];
  plan?: string;
  billingPeriod?: string;
  apiConfiguration?: {
    webhookUrl?: string;
    callbackUrl?: string;
  };
}

export interface IUpdateTenantPayload {
  name?: string;
  type?: TenantType;
  tenantId?: string;
  cacCertificateUrl?: string;
  cbnLicenseUrl?: string;
  contact?: {
    email: string;
    name: string;
    phone?: string;
  };
  branding?: {
    logoUrl?: string;
    faviconUrl?: string;
    primaryColor?: string;
    secondaryColor?: string;
    domain?: string;
  };
  features?: ITenantFeature[];
  plan?: string;
  billingPeriod?: string;
  apiConfiguration?: {
    webhookUrl?: string;
    callbackUrl?: string;
  };
}

export interface ITenantFeature {
  flag: FeatureFlag;
  config: any;
}

export interface ICreateTenantBranchPayload {
  name: string;
  code: string;
  location: string;
  webhookUrl?: string;
  callbackUrl?: string;
  contact: {
    email: string;
    name: string;
    phone?: string;
  };
  features: ITenantFeature[];
}

export interface IUpdateTenantBranchPayload {
  name?: string;
  code?: string;
  location?: string;
  webhookUrl?: string;
  callbackUrl?: string;
  contact?: {
    email: string;
    name: string;
    phone?: string;
  };
  features?: ITenantFeature[];
}
