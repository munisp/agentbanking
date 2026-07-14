import { accountService } from "../../services/accountService";
import { ICreateAccountPayload } from "../../types/account";

export async function createAgentAccountProfile(
  payload: ICreateAccountPayload,
) {
  return accountService.createAccount(payload);
}
