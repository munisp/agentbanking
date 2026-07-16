import { accountService } from "../../services/accountService";
import { ICreateAccountPayload } from "../../types/account";

export async function createMintAccount(payload: ICreateAccountPayload) {
  if (payload.bank?.create)
    await accountService.createBank({
      name: payload.bank.name,
      logo: payload.logo || "",
      tenant_id: payload.tenant_id,
      keycloak_id: payload.keycloak_id,
      ledger_id: payload.ledger_id,
    });
  return accountService.createMintAccount(payload);
}
