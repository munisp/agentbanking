import * as z from "zod";
import { IVerifyFaceResult } from "../types/verification";
import { PostInitializeKycVerificationValidationSchema } from "../validations/schemas";

/**
 * Compare the data submitted by the client with the data returned by shield.
 * @param clientUser The user details submitted 1y the client requesting verification
 * @param user The user data in the shield database
 * @returns
 */
export async function verifyData(
  clientUser: z.infer<
    typeof PostInitializeKycVerificationValidationSchema
  >["user"],
  user: IVerifyFaceResult["ninData"],
) {
  // Possibly extend this to use a more reliable tokenized string comparison method
  return {
    firstName:
      clientUser.firstName.toLocaleLowerCase() ==
      user.firstName.toLocaleLowerCase(),
    lastName:
      clientUser.lastName.toLocaleLowerCase() ==
      user.lastName.toLocaleLowerCase(),
    dateOfBirth: clientUser.dateOfBirth
      ? clientUser.dateOfBirth.toLocaleLowerCase() ==
        user.dateOfBirth.toLocaleLowerCase()
      : false,
    phone:
      clientUser.phone.toLocaleLowerCase() == user.phone.toLocaleLowerCase(),
    UIN: clientUser.UIN.toLocaleLowerCase() == user.nin.toLocaleLowerCase(),
  };
}
