import { authService } from "../../services/authService";
import { ISetupPassword } from "../../types/auth";

export async function setupPassword(payload: ISetupPassword): Promise<void> {
  return authService.setupPassword(payload);
}
