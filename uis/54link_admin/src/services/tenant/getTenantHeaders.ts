import type { Tenant } from './tenantService';

/**
 * Extract required headers from tenant config
 * This is a pure function that doesn't depend on the tenantService instance
 * to avoid circular dependencies
 */
export function getTenantHeaders(tenant: Tenant | null): Record<string, string> {
  if (!tenant) {
    if (import.meta.env.DEV) {
      console.warn('getTenantHeaders: tenant is null');
    }
    // Return default headers if tenant is missing
    return {
      'x-keycloak-id': '6790176f-0cef-4c59-afe7-46459c05c794',
      'x-keycloak-pub-key': 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqo/8w3pBCU0o07mEgMe5sGu94V7W7fj7vgJCItFwVI75QGreP1jI2DpVkgJMw0NKrRzrx5HJ5LG3J34zBzh0Je+ZDIDNnkPuIDViAUO/9wE2Ku3khmURA1RZqOJwkMa95WRbTzOsUCxyKaz5h4PdDuxbSgnUtNcqKQkdEMoOMQUCvRrFJfthqO2nv3IWkhc2JkUZQ9YguKhRbkbXeJsMNmzU/kgdu8cIVpg5buKIUzHxrWiz+mlLzCMm6016GcGlMAYd2+7o9ZQNt5YZ6xDyMP4G4BDou8FrAw5X7+eJHW/WHO91Ap84FWw9GftSIzLeX0NUAWVPzimebfORIzbEPQIDAQAB',
      'x-keycloak-realm': '54link_bpmgd',
      'x-staff-id': 'staff',
      'x-tenant-id': 'bpmgd',
    };
  }

  const headers: Record<string, string> = {};

  // x-tenant-id from tenant.tenant_id or tenant.id
  if (tenant.tenant_id) {
    headers['x-tenant-id'] = tenant.tenant_id||"bpmgd";
  } else if ((tenant as any).id) {
    headers['x-tenant-id'] = String((tenant as any).id);
  } else if (import.meta.env.DEV) {
    console.warn('getTenantHeaders: tenant.tenant_id and tenant.id are missing', tenant);
  }

  // --- Default Keycloak headers ---
  const DEFAULT_KEYCLOAK_ID = '6790176f-0cef-4c59-afe7-46459c05c794';
  const DEFAULT_KEYCLOAK_PUB_KEY = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqo/8w3pBCU0o07mEgMe5sGu94V7W7fj7vgJCItFwVI75QGreP1jI2DpVkgJMw0NKrRzrx5HJ5LG3J34zBzh0Je+ZDIDNnkPuIDViAUO/9wE2Ku3khmURA1RZqOJwkMa95WRbTzOsUCxyKaz5h4PdDuxbSgnUtNcqKQkdEMoOMQUCvRrFJfthqO2nv3IWkhc2JkUZQ9YguKhRbkbXeJsMNmzU/kgdu8cIVpg5buKIUzHxrWiz+mlLzCMm6016GcGlMAYd2+7o9ZQNt5YZ6xDyMP4G4BDou8FrAw5X7+eJHW/WHO91Ap84FWw9GftSIzLeX0NUAWVPzimebfORIzbEPQIDAQAB';
  const DEFAULT_KEYCLOAK_REALM = '54link_bpmgd';

  // Find auth feature flag for Keycloak headers
  const featureFlags = Array.isArray(tenant.feature_flags) ? tenant.feature_flags : [];
  
  if (import.meta.env.DEV) {
    console.log('getTenantHeaders: feature_flags', featureFlags);
    console.log('getTenantHeaders: tenant object', tenant);
  }
  
  const authFeature = featureFlags.find(
    (flag) => flag.name === 'auth'
  );
  
  if (import.meta.env.DEV) {
    console.log('getTenantHeaders: authFeature', authFeature);
  }

  if (authFeature?.config) {
    if (import.meta.env.DEV) {
      console.log('getTenantHeaders: authFeature.config', authFeature.config);
    }

    // x-keycloak-realm from feature_flags.auth.config.realm
    headers['x-keycloak-realm'] = String(authFeature.config.realm || DEFAULT_KEYCLOAK_REALM);

    // x-keycloak-pub-key from feature_flags.auth.config.public_rsa_key
    headers['x-keycloak-pub-key'] = String(authFeature.config.public_rsa_key || DEFAULT_KEYCLOAK_PUB_KEY);

    // x-keycloak-id from feature_flags.auth.config.id or keycloak_id or client_id
    headers['x-keycloak-id'] = String(
      authFeature.config.id ||
      authFeature.config.keycloak_id ||
      authFeature.config.client_id ||
      DEFAULT_KEYCLOAK_ID
    );
  } else {
    // Always set default Keycloak headers if missing
    headers['x-keycloak-realm'] = DEFAULT_KEYCLOAK_REALM;
    headers['x-keycloak-pub-key'] = DEFAULT_KEYCLOAK_PUB_KEY;
    headers['x-keycloak-id'] = DEFAULT_KEYCLOAK_ID;
    if (import.meta.env.DEV) {
      console.warn('getTenantHeaders: authFeature.config is missing, using default Keycloak headers', { authFeature });
    }
  }

  // Find accounts feature flag
  const accountsFeature = featureFlags.find(
    (flag) => flag.name === 'accounts'
  );
  
  if (import.meta.env.DEV) {
    console.log('getTenantHeaders: accountsFeature', accountsFeature);
  }

  if (accountsFeature?.config?.account) {
    const account = accountsFeature.config.account as Record<string, unknown>;

    // x-ledger-id from feature_flags.accounts.config.account.ledger_id
    if (account.ledger_id) {
      headers['x-ledger-id'] = String(account.ledger_id);
    }

    // x-mint-id from feature_flags.accounts.config.account.id
    if (account.id) {
      headers['x-mint-id'] = String(account.id);
    }

    // x-mint-account-id from feature_flags.accounts.config.account.id
    if (account.id) {
      headers['x-mint-account-id'] = String(account.id);
    }
  }

  // x-staff-id = "staff"
  headers['x-staff-id'] = 'staff';

  return headers;
}

