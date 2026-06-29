import { shieldApiClient } from "../lib/ShieldApiClient";
import { InitVerification } from "../types/verification";

export async function initShieldKycVerification(payload: InitVerification) {
  await shieldApiClient.initVerification(payload);
}
