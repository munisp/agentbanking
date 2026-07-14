import * as z from "zod";
import {
  BillingPlan,
  SupportedDatabaseTypes,
  TenantFeatureFlag,
  TenantType,
} from "../utils/enums";

export const EnvSchema = z.object({
  NODE_ENV: z.string(),
  APP_HOST: z.string(),
  APP_PORT: z.coerce.number(),
  LOG_PATH: z.string().optional().default("./logs"),
  LOG_LEVEL: z.string().optional().default("info"),
  LOG_SILENT: z.string().optional().default("false"),
  DB_HOST: z.string(),
  DB_PORT: z.coerce.number(),
  DB_USER: z.string(),
  DB_PASSWORD: z.string(),
  DB_DATABASE: z.string(),
  DB_DATABASE_TYPE: z.nativeEnum(SupportedDatabaseTypes),
  AUTH_SVC_URL: z.string(),
  ACCOUNT_SVC_URL: z.string(),
  ADMIN_SVC_URL: z.string(),
  USER_SVC_URL: z.string(),
  AGENT_SVC_URL: z.string(),
  VERIFICATION_SVC_URL: z.string(),
  VERIFICATION_SVC_IDP: z.string(),
  VERIFICATION_SVC_CLIENT_ID: z.string(),
  VERIFICATION_SVC_CLIENT_SECRET: z.string(),
  DAPR_HOST: z.string(),
  DAPR_HTTP_PORT: z.string(),
  DAPR_PUBSUB_NAME: z.string(),
  DAPR_PUBSUB_TOPIC_PREFIX: z.string(),
  TEMPORAL_ADDRESS: z.string(),
  TEMPORAL_NAMESPACE: z.string(),
  TEMPORAL_TASK_QUEUE: z.string(),
  KEYCLOAK_BASE_URL: z.string(),
  KEYCLOAK_ADMIN_USERNAME: z.string(),
  KEYCLOAK_ADMIN_PASSWORD: z.string(),
  TENANT_SERVICE_APP_ID: z.string(),
});

export const CreateEmployeeSchema = z.object({});

export const CreateCustomerSchema = z.object({
  email: z.string(),
  firstName: z.string(),
  lastName: z.string(),
  phone: z.string(),
  uin: z.string(),
  password: z.string(),
  address: z.string(),
  city: z.string(),
  state: z.string(),
  postalCode: z.string(),
});

export const KycCustomerCallbackSchema = z.object({
  id: z.string(),
  faceVerificationResult: z
    .object({
      success: z.boolean(),
      similarity: z.number(),
    })
    .optional(),
  dataVerificationResult: z
    .object({
      firstName: z.boolean(),
      lastName: z.boolean(),
      phone: z.boolean(),
      dateOfBirth: z.boolean(),
      UIN: z.boolean(),
    })
    .optional(),
  score: z.number(),
  metadata: z.object({
    keycloak_id: z.string(),
    tenant_id: z.string(),
    is_admin: z.boolean().optional(),
    is_agent: z.boolean().optional(),
    first_name: z.string().optional(),
    last_name: z.string().optional(),
  }),
});

export const KycAgentCallbackSchema = z.object({
  id: z.string(),
  faceVerificationResult: z
    .object({
      success: z.boolean(),
      similarity: z.number(),
    })
    .optional(),
  dataVerificationResult: z
    .object({
      firstName: z.boolean(),
      lastName: z.boolean(),
      phone: z.boolean(),
      dateOfBirth: z.boolean(),
      UIN: z.boolean(),
    })
    .optional(),
  score: z.number(),
  metadata: z.object({
    keycloak_id: z.string(),
    tenant_id: z.string(),
    first_name: z.string().optional(),
    last_name: z.string().optional(),
  }),
});

export const CreateTenantSchema = z.object({
  name: z.string(),
  type: z.nativeEnum(TenantType),
  contact: CreateCustomerSchema,
  cacCertificateUrl: z.string().optional(),
  cbnLicenseUrl: z.string().optional(),
  branding: z
    .object({
      logoUrl: z.string().optional(),
      faviconUrl: z.string().optional(),
      primaryColor: z.string().optional(),
      secondaryColor: z.string().optional(),
      domain: z.string().optional(),
    })
    .optional(),
  featureFlags: z.array(z.nativeEnum(TenantFeatureFlag)).optional(),
  plan: z.nativeEnum(BillingPlan).optional(),
  apiConfiguration: z
    .object({
      webhookUrl: z.string().optional(),
      callbackUrl: z.string().optional(),
    })
    .optional(),
});

export const CreateAdminSchema = z.object({
  email: z.string().email(),
  firstName: z.string(),
  lastName: z.string(),
  phone: z.string(),
  uin: z.string(),
  password: z.string().optional(),
  accessLevel: z.string().optional(),
});

export const CreateAgentSchema = z.object({
  email: z.string().email(),
  firstName: z.string(),
  lastName: z.string(),
  phone: z.string(),
  uin: z.string(),
  password: z.string(),
  agentRole: z.string().optional(),
  businessName: z.string().optional(),
  businessAddress: z.string().optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  postalCode: z.string().optional(),
  lga: z.string().optional(),
});
