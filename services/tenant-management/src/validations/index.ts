import { ApiError } from "../middlewares/error";
import * as z from "zod";
import httpStatus from "http-status";
import logger from "../config/logger.config";
import { BillingPeriod, BillingPlan, FeatureFlag, TenantType } from "../utils/enums";

export function validateRequest<T>(schema: z.ZodType<T>, payload: object) {
  try {
    schema.parse(payload);
    return payload as z.infer<typeof schema>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (e: any) {
    logger.error("Validation error: %o", e);
    throw new ApiError(httpStatus.UNPROCESSABLE_ENTITY, e.message ?? "Validation error");
  }
}

export const PostCreateTenantSchema = z.object({
  name: z.string(),
  type: z.nativeEnum(TenantType),
  cacCertificateUrl: z.string().optional(),
  cbnLicenseUrl: z.string().optional(),
  contact: z.object({
    email: z.string(),
    name: z.string(),
    phone: z.string().optional(),
  }),
  branding: z
    .object({
      logoUrl: z.string().optional(),
      faviconUrl: z.string().optional(),
      primaryColor: z.string().optional(),
      secondaryColor: z.string().optional(),
      domain: z.string().optional(),
    })
    .optional(),
  features: z.array(
    z.object({
      flag: z.nativeEnum(FeatureFlag),
      config: z.record(z.any()),
    })
  ),
  plan: z.nativeEnum(BillingPlan).optional(),
  billingPeriod: z.nativeEnum(BillingPeriod).optional(),
  apiConfiguration: z
    .object({
      webhookUrl: z.string().optional(),
      callbackUrl: z.string().optional(),
    })
    .optional(),
});

export const PutUpdateTenantSchema = z.object({
  name: z.string().optional(),
  type: z.nativeEnum(TenantType).optional(),
  cacCertificateUrl: z.string().optional(),
  cbnLicenseUrl: z.string().optional(),
  contact: z
    .object({
      email: z.string(),
      name: z.string(),
      phone: z.string().optional(),
    })
    .optional(),
  branding: z
    .object({
      logoUrl: z.string().optional(),
      faviconUrl: z.string().optional(),
      primaryColor: z.string().optional(),
      secondaryColor: z.string().optional(),
      domain: z.string().optional(),
    })
    .optional(),
  features: z
    .array(
      z.object({
        flag: z.nativeEnum(FeatureFlag),
        config: z.record(z.any()),
      })
    )
    .optional(),
  plan: z.nativeEnum(BillingPlan).optional(),
  billingPeriod: z.nativeEnum(BillingPeriod).optional(),
  apiConfiguration: z
    .object({
      webhookUrl: z.string().optional(),
      callbackUrl: z.string().optional(),
    })
    .optional(),
});

export const PostCreateBranchSchema = z.object({
  name: z.string(),
  code: z.string(),
  location: z.string(),
  webhookUrl: z.string().optional(),
  callbackUrl: z.string().optional(),
  contact: z.object({
    email: z.string(),
    name: z.string(),
    phone: z.string().optional(),
  }),
  features: z.array(
    z.object({
      flag: z.nativeEnum(FeatureFlag),
      config: z.record(z.any()),
    })
  ),
});

export const PutUpdateBranchSchema = z.object({
  name: z.string().optional(),
  code: z.string().optional(),
  location: z.string().optional(),
  webhookUrl: z.string().optional(),
  callbackUrl: z.string().optional(),
  contact: z
    .object({
      email: z.string(),
      name: z.string(),
      phone: z.string().optional(),
    })
    .optional(),
  features: z
    .array(
      z.object({
        flag: z.nativeEnum(FeatureFlag),
        config: z.record(z.any()),
      })
    )
    .optional(),
});
