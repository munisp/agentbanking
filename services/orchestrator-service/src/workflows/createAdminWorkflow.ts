import { ApplicationFailure, proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { ICreateAdminWorkflow } from "../types/workflows";
import { DEFAULT_ADMIN_PASSWORD } from "../utils/constants";
import {
  CustomerRole,
  NotificationCategory,
  NotificationType,
} from "../utils/enums";

export async function createAdminWorkflow(
  args: ICreateAdminWorkflow,
): Promise<string> {
  const {
    createAuthProfile,
    createAdminProfile,
    sendEmail,
    initializeKyc,
    setupPassword,
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
    // 01a. Create Auth Profile with named Permify role (v2.perm)
    const auth = await createAuthProfile({
      email: args.email,
      user_role: CustomerRole.ADMIN,
      tenant_id: args.tenantId,
      keycloak_realm: args.keycloakRealm,
      keycloak_pub_key: args.keycloakPublicKey,
      platform_role: args.platformRole, // v2.perm platform role
      tenant_role: args.tenantRole, // v2.perm tenants role
    });

    // 01b. Setup Password
    await setupPassword({
      keycloak_id: auth.auth.keycloak_id,
      password: args.password || DEFAULT_ADMIN_PASSWORD,
      confirm_password: args.password || DEFAULT_ADMIN_PASSWORD,
      tenant_id: args.tenantId,
      keycloak_realm: args.keycloakRealm,
      keycloak_pub_key: args.keycloakPublicKey,
    });

    // 02. Create Admin Profile
    await createAdminProfile({
      first_name: args.firstName,
      last_name: args.lastName,
      email: args.email,
      phone: args.phone,
      uin: args.uin,
      keycloak_id: auth.auth.keycloak_id,
      platform_role: args.platformRole,
      tenant_role: args.tenantRole,
      tenant_id: args.tenantId,
    });

    // 03. Create Notification Profile & Send Password Update Email
    await sendEmail({
      createSubscriber: true,
      category: NotificationCategory.EMAIL,
      payload: {
        url: "",
      },
      subscriberId: `${args.tenantId}_${auth.auth.keycloak_id}`,
      type: NotificationType.WELCOME_EMAIL,
      subscriber: {
        subscriberId: `${args.tenantId}_${auth.auth.keycloak_id}`,
        traits: {
          email: args.email,
          phone: args.phone,
          firstName: args.firstName,
          lastName: args.lastName,
        },
      },
    });

    // 04. Initialize Kyc with verification service
    const kyc = await initializeKyc({
      user: {
        firstName: args.firstName,
        lastName: args.lastName,
        phone: args.phone,
        UIN: args.uin,
      },
      metadata: {
        keycloak_id: auth.auth.keycloak_id,
        tenant_id: args.tenantId,
        is_admin: true,
      },
    });

    // 05. Send KYC Email
    await sendEmail({
      createSubscriber: false,
      category: NotificationCategory.EMAIL,
      payload: {
        id: kyc.id,
        url: kyc.url,
      },
      subscriberId: `${args.tenantId}_${auth.auth.keycloak_id}`,
      type: NotificationType.KYC,
    });

    // 06. Save KYC State in Admin Service

    await saveAdminKycState(kyc.url, args.tenantId, auth.auth.keycloak_id);

    return kyc.url;
  } catch (e: any) {
    throw new ApplicationFailure(e.message);
  }
}
