import { readEnv } from "../config/readEnv.config";
import { ClientEntity } from "../entity/ClientEntity";
import { ballerineApiClient } from "../lib/BallerineApiClient";
import * as z from "zod";
import { PostInitializeVerificationValidationSchema } from "../validations/schemas";
import { BallerineWorkflow } from "../types/workflow";

/**
 *
 * @param payload
 * @param client
 * @param ballerineBusinessId
 * @returns BallerineWorkflow
 */
export async function createBallerineWorkflow(
  payload: z.infer<typeof PostInitializeVerificationValidationSchema>,
  client: ClientEntity,
  ballerineBusinessId: string
): Promise<BallerineWorkflow> {
  return await ballerineApiClient.createWorkflow(
    readEnv("DEFAULT_KYB_WORKFLOW_ID"),
    {
      entity: {
        type: "business",
        id: ballerineBusinessId,
        data: {
          country: payload.address.country,
          registrationNumber: payload.registrationNumber,
          companyName: payload.companyName,
          additionalInfo: {
            mainRepresentative: {
              email: payload.contact.email,
              firstName: payload.contact.firstName,
              lastName: payload.contact.lastName,
            },
          },
        },
      },
    },
    {},
    client.ballerine_customer_api_key
  );
}
