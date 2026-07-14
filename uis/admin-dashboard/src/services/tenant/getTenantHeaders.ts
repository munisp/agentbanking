import type { Tenant } from "./tenantService";

/**
 * Extract required headers from tenant config
 * This is a pure function that doesn't depend on the tenantService instance
 * to avoid circular dependencies
 */
export function getTenantHeaders(
  tenant: Tenant | null,
): Record<string, string> {
  if (!tenant) {
    if (import.meta.env.DEV) {
      console.warn("getTenantHeaders: tenant is null");
    }
    return {};
  }

  const headers: Record<string, string> = {};

  // x-tenant-id from tenant.tenant_id or tenant.id
  if (tenant.tenant_id) {
    headers["x-tenant-id"] = tenant.tenant_id;
  } else if ((tenant as any).id) {
    headers["x-tenant-id"] = String((tenant as any).id);
  } else if (import.meta.env.DEV) {
    console.warn(
      "getTenantHeaders: tenant.tenant_id and tenant.id are missing",
      tenant,
    );
  }

  // Find auth feature flag for Keycloak headers
  const featureFlags = Array.isArray(tenant.feature_flags)
    ? tenant.feature_flags
    : [];

  if (import.meta.env.DEV) {
    console.log("getTenantHeaders: feature_flags", featureFlags);
    console.log("getTenantHeaders: tenant object", tenant);
  }

  const authFeature = featureFlags.find((flag) => flag.name === "auth");

  if (import.meta.env.DEV) {
    console.log("getTenantHeaders: authFeature", authFeature);
  }

  if (authFeature?.config) {
    if (import.meta.env.DEV) {
      console.log("getTenantHeaders: authFeature.config", authFeature.config);
    }

    // x-keycloak-realm from feature_flags.auth.config.realm
    if (authFeature.config.realm) {
      headers["x-keycloak-realm"] = String(authFeature.config.realm);
    }

    // x-keycloak-pub-key from feature_flags.auth.config.public_rsa_key
    if (authFeature.config.public_rsa_key) {
      headers["x-keycloak-pub-key"] = String(authFeature.config.public_rsa_key);
    }

    // x-keycloak-id from feature_flags.auth.config.id or keycloak_id or client_id
    if (authFeature.config.id) {
      headers["x-keycloak-id"] = String(authFeature.config.id);
    } else if (authFeature.config.keycloak_id) {
      headers["x-keycloak-id"] = String(authFeature.config.keycloak_id);
    } else if (authFeature.config.client_id) {
      headers["x-keycloak-id"] = String(authFeature.config.client_id);
    } else if (import.meta.env.DEV) {
      console.warn(
        "getTenantHeaders: x-keycloak-id not found in authFeature.config",
        {
          config: authFeature.config,
          availableKeys: Object.keys(authFeature.config),
        },
      );
    }
  } else if (import.meta.env.DEV) {
    console.warn("getTenantHeaders: authFeature.config is missing", {
      authFeature,
    });
  }

  // Find accounts feature flag
  const accountsFeature = featureFlags.find((flag) => flag.name === "accounts");

  if (import.meta.env.DEV) {
    console.log("getTenantHeaders: accountsFeature", accountsFeature);
  }

  if (accountsFeature?.config?.account) {
    const account = accountsFeature.config.account as Record<string, unknown>;

    // x-ledger-id from feature_flags.accounts.config.account.ledger_id
    if (account.ledger_id) {
      headers["x-ledger-id"] = String(account.ledger_id);
    }

    // x-mint-id from feature_flags.accounts.config.account.id
    if (account.id) {
      headers["x-mint-id"] = String(account.id);
    }

    // x-mint-account-id from feature_flags.accounts.config.account.id
    if (account.id) {
      headers["x-mint-account-id"] = String(account.id);
    }
  }

  // x-staff-id = "staff"
  headers["x-staff-id"] = "staff";

  return headers;
}
