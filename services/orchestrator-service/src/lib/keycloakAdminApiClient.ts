import axios, { Axios } from "axios";
import * as https from "https";
import winston from "winston";
import { readEnv } from "../config/readEnv.config";
import logger from "../config/logger.config";
import { IKeycloakKeyConfig } from "../types/keycloak";

const httpsAgent = new https.Agent({
  rejectUnauthorized: false,
});

export class KeycloakAdminApiClient {
  private static instance: KeycloakAdminApiClient;
  private readonly axios_client: Axios;
  private readonly logger: winston.Logger;

  private token: string | null = null;
  private expires_at: number = 0;

  private constructor() {
    this.axios_client = axios.create({
      baseURL: readEnv("KEYCLOAK_BASE_URL"),
      httpsAgent,
    });
    this.logger = logger;
  }

  public static get_instance(): KeycloakAdminApiClient {
    if (!KeycloakAdminApiClient.instance) {
      KeycloakAdminApiClient.instance = new KeycloakAdminApiClient();
    }
    return KeycloakAdminApiClient.instance;
  }

  private async request_token() {
    const now = Date.now();

    // If token is still valid, return cached token
    if (this.token && this.expires_at > now) {
      return this.token;
    }

    const headers = {
      "Content-Type": "application/x-www-form-urlencoded",
    };

    const params = new URLSearchParams();

    params.append("grant_type", "password");
    params.append("username", readEnv("KEYCLOAK_ADMIN_USERNAME"));
    params.append("password", readEnv("KEYCLOAK_ADMIN_PASSWORD"));
    params.append("client_id", "admin-cli");

    const response = await this.axios_client.post(
      `/realms/master/protocol/openid-connect/token`,
      params.toString(),
      { headers }
    );

    const { access_token, expires_in } = response.data;

    this.token = access_token;
    this.expires_at = now + (expires_in - 10) * 1000;

    return this.token;
  }

  private async get_config() {
    const headers = {
      Authorization: `Bearer ${await this.request_token()}`,
    };

    return { headers };
  }

  public async create_realm(realm_name: string) {
    try {
      const { data } = await this.axios_client.post(
        "/admin/realms",
        {
          realm: realm_name,
          bruteForceProtected: true,
          permanentLockout: false,
          enabled: true,
          maxFailureWaitSeconds: 3600,
          minimumQuickLoginWaitSeconds: 60,
          maxDeltaTimeSeconds: 3600,
          waitIncrementSeconds: 60,
          failureFactor: 5,
          requiredActions: [
            {
              alias: "CONFIGURE_TOTP",
              name: "Configure OTP",
              providerId: "CONFIGURE_TOTP",
              enabled: true,
              defaultAction: false,
              priority: 10,
              config: {},
            },
            {
              alias: "TERMS_AND_CONDITIONS",
              name: "Terms and Conditions",
              providerId: "TERMS_AND_CONDITIONS",
              enabled: false,
              defaultAction: false,
              priority: 20,
              config: {},
            },
            {
              alias: "UPDATE_PASSWORD",
              name: "Update Password",
              providerId: "UPDATE_PASSWORD",
              enabled: true,
              defaultAction: false,
              priority: 30,
              config: {},
            },
            {
              alias: "UPDATE_PROFILE",
              name: "Update Profile",
              providerId: "UPDATE_PROFILE",
              enabled: true,
              defaultAction: false,
              priority: 40,
              config: {},
            },
            {
              alias: "VERIFY_EMAIL",
              name: "Verify Email",
              providerId: "VERIFY_EMAIL",
              enabled: true,
              defaultAction: false,
              priority: 50,
              config: {},
            },
            {
              alias: "delete_account",
              name: "Delete Account",
              providerId: "delete_account",
              enabled: false,
              defaultAction: false,
              priority: 60,
              config: {},
            },
            {
              alias: "webauthn-register",
              name: "Webauthn Register",
              providerId: "webauthn-register",
              enabled: true,
              defaultAction: false,
              priority: 70,
              config: {},
            },
            {
              alias: "webauthn-register-passwordless",
              name: "Webauthn Register Passwordless",
              providerId: "webauthn-register-passwordless",
              enabled: true,
              defaultAction: false,
              priority: 80,
              config: {},
            },
            {
              alias: "update_user_locale",
              name: "Update User Locale",
              providerId: "update_user_locale",
              enabled: true,
              defaultAction: false,
              priority: 1000,
              config: {},
            },
          ],
          rememberMe: false,
          verifyEmail: false,
          loginWithEmailAllowed: true,
          requiredCredentials: ["password"],
          accessTokenLifespanForImplicitFlow: 7200,
          ssoSessionIdleTimeout: 7200,
          ssoSessionMaxLifespan: 36000,
          accessTokenLifespan: 7200,
          passwordPolicy:
            "forceExpiredPasswordChange(60) and length(6) and specialChars(1) and digits(1) and notEmail(undefined)",
        },
        await this.get_config()
      );

      this.logger.info({
        message: "Realm created successfully",
        data,
      });
    } catch (e: any) {
      if (e.response?.status === 400) {
        return; // Ignore error - Realm already exists;
      }
      throw e;
    }
  }

  private async get_keys(tenant_id: string) {
    const { data } = await this.axios_client.get<IKeycloakKeyConfig>(
      `/admin/realms/${tenant_id}/keys`,
      await this.get_config()
    );

    return data;
  }

  public async get_public_rsa_key(tenant_id: string) {
    const { keys, active } = await this.get_keys(tenant_id);

    const key_id = active.RS256;

    if (!key_id) {
      throw new Error("RS256 key is not active");
    }

    const publicKey = keys.find((e) => e.kid === key_id);

    if (!publicKey) {
      throw new Error("RS256 key is not active");
    }

    return publicKey.publicKey;
  }

  public async delete_realm(realm_name: string) {
    await this.axios_client.delete(`/admin/realms/${realm_name}`, await this.get_config());
  }

  private async get_basic_client_scope_id(realm: string): Promise<string> {
    const { data } = await this.axios_client.get(
      `/admin/realms/${realm}/client-scopes`,
      await this.get_config()
    );

    const basicScope = data.find((s: any) => s.name === "basic");

    if (!basicScope) {
      throw new Error("Basic client scope not found");
    }

    return basicScope.id;
  }

  private async get_sub_mapper(realm: string, scopeId: string) {
    const { data } = await this.axios_client.get(
      `/admin/realms/${realm}/client-scopes/${scopeId}/protocol-mappers/models`,
      await this.get_config()
    );

    return data.find((m: any) => m.name === "sub");
  }

  public async enable_sub_in_lightweight_token(realm: string) {
    const scopeId = await this.get_basic_client_scope_id(realm);
    const subMapper = await this.get_sub_mapper(realm, scopeId);

    if (!subMapper) {
      throw new Error("sub protocol mapper not found");
    }

    // Idempotent check
    if (subMapper.config?.["add.to.lightweight.access.token"] === "true") {
      return;
    }

    await this.axios_client.put(
      `/admin/realms/${realm}/client-scopes/${scopeId}/protocol-mappers/models/${subMapper.id}`,
      {
        ...subMapper,
        config: {
          "access.token.claim": "true",
          "add.to.lightweight.access.token": "true",
          "introspection.token.claim": "true",
          "lightweight.claim": "true",
        },
      },
      await this.get_config()
    );
  }
}
