import { ApplicationFailure, proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { ICreateAgentWorkflow } from "../types/workflows";
import {
  CustomerRole,
  NotificationCategory,
  NotificationType,
} from "../utils/enums";

export async function createAgentWorkflow(
  args: ICreateAgentWorkflow,
): Promise<string> {
  const {
    createAuthProfile,
    createAgentProfile,
    sendEmail,
    initializeKyc,
    setupPassword,
    saveAgentKycState,
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
    // 01a. Create Auth Profile with USER role (agent-specific role tracked in agent service)
    const auth = await createAuthProfile({
      email: args.email,
      user_role: CustomerRole.USER,
      tenant_id: args.tenantId,
      keycloak_realm: args.keycloakRealm,
      keycloak_pub_key: args.keycloakPublicKey,
    });

    // 01b. Setup Password
    await setupPassword({
      keycloak_id: auth.auth.keycloak_id,
      password: args.password,
      confirm_password: args.password,
      tenant_id: args.tenantId,
      keycloak_realm: args.keycloakRealm,
      keycloak_pub_key: args.keycloakPublicKey,
    });

    // 02. Create Agent Profile in Agent Service (54agent namespace)
    await createAgentProfile({
      first_name: args.firstName,
      last_name: args.lastName,
      email: args.email,
      phone: args.phone,
      uin: args.uin,
      keycloak_id: auth.auth.keycloak_id,
      tenant_id: args.tenantId,
      agent_role: args.agentRole,
      business_name: args.businessName,
      business_address: args.businessAddress,
      city: args.city,
      state: args.state,
      postal_code: args.postalCode,
      lga: args.lga,
    });

    // 03. Create Notification Profile & Send Welcome Email
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

    // 04. Initialize KYC with verification service
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
        is_agent: true, // Flag to route to agent callback
        first_name: args.firstName,
        last_name: args.lastName,
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

    // 06. Save KYC State in Agent Service
    await saveAgentKycState(kyc.url, args.tenantId, auth.auth.keycloak_id);

    return kyc.url;
  } catch (e: unknown) {
    const error = e as Error;
    throw new ApplicationFailure(error.message);
  }
}
