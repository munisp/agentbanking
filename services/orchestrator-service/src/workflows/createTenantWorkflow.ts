import { ApplicationFailure, proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { ITenant } from "../types/tenant";
import { ICreateTenantWorkflow } from "../types/workflows";
import {
  CustomerRole,
  NotificationCategory,
  NotificationType,
  TenantFeatureFlag,
  TenantStatus,
  TenantType,
} from "../utils/enums";

export async function createTenantWorkflow(
  args: ICreateTenantWorkflow,
): Promise<ITenant> {
  const {
    applyRequiredFeatureFlags,
    provisionKeycloakRealm,
    sendEmail,
    createTenant,
    createMintAccount,
    createAuthProfile,
    createUserProfile,
    getTenant,
    setupPassword,
    initializeKyc,
    createAdminProfile,
    saveAdminKycState,
  } = proxyActivities<typeof activities>({
    retry: {
      initialInterval: "1s",
      maximumInterval: "1m",
      backoffCoefficient: 2,
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "1m",
  });

  try {
    // 00. Check if tenant already exists and has completed onboarding and exit gracefully.
    // No side effects
    let tenant = await getTenant(args.tenantId);
    if (tenant && tenant.status != TenantStatus.ONBOARDING)
      throw new Error("Tenant already exists.");

    // 01. Initialize required feature flags for tenant.
    // No side effects
    const feature_flags = await applyRequiredFeatureFlags(args.featureFlags);

    // 02. Initialize features array
    const features = feature_flags.map((feature_flag) => ({
      flag: feature_flag,
      config: {},
    }));

    // 03. Setup Auth Feature
    // Create keycloak realm and save config
    const keycloakConfig = await provisionKeycloakRealm(
      `54agent_${args.tenantId}`,
    );
    const authFeature = features.find(
      (feature) => feature.flag === TenantFeatureFlag.AUTH,
    );
    if (authFeature) authFeature.config = keycloakConfig;

    // 04. Setup Account Feature
    // Create mint account and save config
    const mintAccountConfig = await createMintAccount({
      name: `mint_account_${args.tenantId}`,
      keycloak_id: `mint_account_${args.tenantId}`,
      ledger_id: args.ledgerId,
      tenant_id: args.tenantId,
      bank: {
        create:
          args.type == TenantType.BANK || args.type == TenantType.MICROFINANCE,
        name: args.name,
        logo: args.branding?.logoUrl || "",
      },
    });
    const accountFeature = features.find(
      (feature) => feature.flag === TenantFeatureFlag.ACCOUNTS,
    );
    if (accountFeature) accountFeature.config = mintAccountConfig;

    // 05. Create Tenant Record in Tenant Service
    tenant = await createTenant({
      ...args,
      tenantId: args.tenantId,
      contact: {
        ...args.contact,
        phone: args.contact.phone,
        name: args.contact.firstName + " " + args.contact.lastName,
      },
      features,
    });

    // 06a. Create Contact Auth Profile
    const auth = await createAuthProfile({
      email: args.contact.email,
      user_role: args.contact.role || CustomerRole.ADMIN,
      tenant_id: args.tenantId,
      keycloak_realm: keycloakConfig.realm,
      keycloak_pub_key: keycloakConfig.public_rsa_key,
    });

    // 06b. Setup Password
    await setupPassword({
      keycloak_id: auth.auth.keycloak_id,
      password: args.contact.password,
      confirm_password: args.contact.password,
      tenant_id: args.tenantId,
      keycloak_realm: keycloakConfig.realm,
      keycloak_pub_key: keycloakConfig.public_rsa_key,
    });

    // 07. Create Contact Customer Profile
    // await createUserProfile({
    //   first_name: args.contact.firstName,
    //   last_name: args.contact.lastName,
    //   email: args.contact.email,
    //   phone: args.contact.phone,
    //   uin: args.contact.uin,
    //   keycloak_id: auth.auth.keycloak_id,
    //   tenant_id: args.tenantId,
    //   address: args.contact.address,
    //   city: args.contact.city,
    //   state: args.contact.state,
    //   postal_code: args.contact.postalCode,
    // });
    await createAdminProfile({
      first_name: args.contact.firstName,
      last_name: args.contact.lastName,
      email: args.contact.email,
      phone: args.contact.phone,
      uin: args.contact.uin,
      keycloak_id: auth.auth.keycloak_id,
      tenant_role: "super_admin", // Tenant contact is super_admin on the tenants entity (v2.perm)
      tenant_id: args.tenantId,
    });

    // 08. Send Welcome Email to Contact
    await sendEmail({
      createSubscriber: true,
      category: NotificationCategory.EMAIL,
      payload: {
        url: "",
      },
      subscriberId: `54agent_tenant_${args.tenantId}_contact`,
      type: NotificationType.WELCOME_EMAIL,
      subscriber: {
        subscriberId: `54agent_tenant_${args.tenantId}_contact`,
        traits: {
          email: args.contact.email,
          phone: args.contact.phone,
        },
      },
    });

    // 09. Initialize Admin KYC
    const kyc = await initializeKyc({
      user: {
        firstName: args.contact.firstName,
        lastName: args.contact.lastName,
        phone: args.contact.phone,
        UIN: args.contact.uin,
      },
      metadata: {
        keycloak_id: auth.auth.keycloak_id,
        tenant_id: args.tenantId,
        is_admin: true,
      },
    });

    // 10. Save Admin KYC State
    await saveAdminKycState(kyc.url, args.tenantId, auth.auth.keycloak_id);

    return { ...tenant, kyc_url: kyc.url };
  } catch (e: any) {
    throw new ApplicationFailure(e.message);
  }
}
