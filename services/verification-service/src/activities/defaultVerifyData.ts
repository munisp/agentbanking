import * as z from "zod";
import { PostInitializeKycVerificationValidationSchema } from "../validations/schemas";
import { IVerifyFaceResult } from "../types/verification";
import { assertKycSimulationMode } from "../utils/kycSimulationMode";

/**
 * Compare the data submitted by the client with the data returned after verification.
 *
 * SIMULATION ONLY: without a real verification provider this just compares
 * user input against itself, which can never constitute verification. It is
 * hard-gated behind KYC simulation mode and must never run in production.
 * @param clientUser The user details submitted 1y the client requesting verification
 * @param user The user data in the database
 * @returns
 */
export async function defaultVerifyData(
  clientUser: z.infer<typeof PostInitializeKycVerificationValidationSchema>["user"],
  user: IVerifyFaceResult["ninData"]
) {
  // Fail closed: never produce a fabricated comparison outside simulation mode.
  assertKycSimulationMode("defaultVerifyData");

  // Possibly extend this to use a more reliable tokenized string comparison method
  return {
    firstName: clientUser.firstName.toLocaleLowerCase() == user.firstName.toLocaleLowerCase(),
    lastName: clientUser.lastName.toLocaleLowerCase() == user.lastName.toLocaleLowerCase(),
    dateOfBirth: clientUser.dateOfBirth
      ? clientUser.dateOfBirth.toLocaleLowerCase() == user.dateOfBirth.toLocaleLowerCase()
      : false,
    phone: clientUser.phone.toLocaleLowerCase() == user.phone.toLocaleLowerCase(),
    UIN: clientUser.UIN.toLocaleLowerCase() == user.nin.toLocaleLowerCase(),
  };
}
