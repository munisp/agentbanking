import * as z from "zod";
import { KycIdentityProviders, KycVerificationImageTypeEnum } from "../utils/enums";

export const EnvSchema = z.object({
  APP_HOST: z.string(),
  APP_PORT: z.coerce.number(),
  SHIELD_API_URL: z.string().optional(),
  LOG_PATH: z.string().optional(),
  LOG_LEVEL: z.string().optional(),
  LOG_SILENT: z.string().optional(),
  DB_HOST: z.string(),
  DB_PORT: z.string(),
  DB_USER: z.string(),
  DB_PASSWORD: z.string(),
  DB_DATABASE: z.string(),
  DB_DATABASE_TYPE: z.enum(["postgres", "mysql"]),
  DB_SSL_ENABLED: z.string().optional(),
  BALLERINE_API_URL: z.string(),
  BALLERINE_API_KEY: z.string(),
  DEFAULT_KYB_WORKFLOW_ID: z.string(),
  TEMPORAL_NAMESPACE: z.string(),
  TEMPORAL_TASK_QUEUE: z.string(),
  TEMPORAL_ADDRESS: z.string(),
  KYB_COLLECTION_FLOW_BASE_URL: z.string(),
  KYC_FLOW_BASE_URL: z.string(),
  SHIELD_VERIFICATION_BASE_URL: z.string(),
  SHIELD_VERIFICATION_API_KEY: z.string(),
  KYC_FLOW_API_KEY: z.string(),
});

export const ContactValidationSchema = z.object({
  firstName: z.string(),
  lastName: z.string(),
  email: z.string(),
});

export const PostRegisterClientValidationSchema = z.object({
  clientName: z.string().trim().nonempty(),
  redirectUrls: z.string().trim().array(),
  contact: ContactValidationSchema,
  logo: z.string().optional(),
  callBackUrl: z.string().optional(),
});

export const PostInitializeVerificationValidationSchema = z.object({
  companyName: z.string(),
  registrationNumber: z.string(),
  mccCode: z.string().length(3),
  businessType: z.string(),
  address: z.object({
    country: z.string(),
    countryCode: z.string(),
    city: z.string(),
    street: z.string(),
    postcode: z.string(),
    state: z.string(),
  }),
  contact: ContactValidationSchema,
});

export const PostInitializeKycVerificationValidationSchema = z.object({
  identityProvider: z.nativeEnum(KycIdentityProviders).default(KycIdentityProviders.LIVENESS),
  user: z.object({
    firstName: z.string().trim().nonempty(),
    lastName: z.string().trim().nonempty(),
    phone: z.string().trim().nonempty(),
    UIN: z.string().trim().nonempty(),
    dateOfBirth: z.string().trim().optional(),
  }),
  redirectUrl: z.string().optional(),
  metadata: z.any().optional(),
});

export const PostVerifyKycValidationSchema = z.object({
  endUserInfo: z.object({
    id: z.string(),
  }),
  document: z.object({
    type: z.string(),
    country: z.string(),
    frontImage: z.string(),
    backImage: z.string(),
  }).optional(),
  selfie: z.object({
    image: z.string(),
  }).optional(),
  livenessProof: z.object({
    sessionId: z.string(),
    timestamp: z.number(),
    confidence: z.number(),
    verdict: z.string(),
    signals: z.object({
      motion: z.number(),
      challengePassed: z.boolean(),
      timingVariance: z.number(),
      lightVariance: z.number(),
      frameDiff: z.number(),
    }),
    hash: z.string(),
  }).optional(),
  documents: z.array(
    z.object({
      type: z.nativeEnum(KycVerificationImageTypeEnum),
      pages: z.array(
        z.object({
          base64: z.string(),
        })
      ),
    })
  ).optional(),
  metadata: z.any().optional(),
});
