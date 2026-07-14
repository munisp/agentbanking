import { TenantFeatureFlag } from "../../utils/enums";

export async function applyRequiredFeatureFlags(featureFlags?: TenantFeatureFlag[]) {
  const requiredFlags = [
    TenantFeatureFlag.AUTH,
    TenantFeatureFlag.USER_MANAGEMENT,
    TenantFeatureFlag.ACCOUNTS,
    TenantFeatureFlag.REPORTING,
  ];

  return Array.from(new Set([...(featureFlags || []), ...requiredFlags]));
}
