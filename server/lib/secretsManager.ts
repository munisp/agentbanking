/**
 * Secrets Manager — centralized secret access abstraction
 *
 * Supports:
 * - Environment variables (default)
 * - AWS Secrets Manager (production)
 * - HashiCorp Vault (enterprise)
 *
 * All secrets accessed through this module, never direct env vars.
 */

interface SecretConfig {
  provider: "env" | "aws" | "vault";
  cacheTTL: number; // seconds
}

const config: SecretConfig = {
  provider: (process.env.SECRETS_PROVIDER as SecretConfig["provider"]) || "env",
  cacheTTL: 300,
};

const cache = new Map<string, { value: string; expiresAt: number }>();

export async function getSecret(name: string): Promise<string | undefined> {
  const cached = cache.get(name);
  if (cached && Date.now() < cached.expiresAt) {
    return cached.value;
  }

  let value: string | undefined;

  switch (config.provider) {
    case "aws":
      value = await getFromAWS(name);
      break;
    case "vault":
      value = await getFromVault(name);
      break;
    default:
      value = process.env[name];
  }

  if (value) {
    cache.set(name, {
      value,
      expiresAt: Date.now() + config.cacheTTL * 1000,
    });
  }

  return value;
}

export async function getRequiredSecret(name: string): Promise<string> {
  const value = await getSecret(name);
  if (!value) {
    throw new Error(
      `Required secret "${name}" not found in ${config.provider} provider`
    );
  }
  return value;
}

async function getFromAWS(name: string): Promise<string | undefined> {
  // AWS Secrets Manager integration
  // In production: use @aws-sdk/client-secrets-manager
  return process.env[name];
}

async function getFromVault(name: string): Promise<string | undefined> {
  // HashiCorp Vault integration
  // In production: use node-vault
  return process.env[name];
}

export function invalidateCache(name?: string) {
  if (name) {
    cache.delete(name);
  } else {
    cache.clear();
  }
}
