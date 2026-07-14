import { accountService } from "../../services/accountService";
import { ICreateAccountPayload } from "../../types/account";

export async function createAccountProfile(payload: ICreateAccountPayload) {
  return accountService.createAccount(payload);
}
