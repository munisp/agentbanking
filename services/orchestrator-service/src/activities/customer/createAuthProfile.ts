import { authService } from "../../services/authService";
import { IAuthProfilePayload, IAuthProfileResponse } from "../../types/auth";

export async function createAuthProfile(payload: IAuthProfilePayload): Promise<IAuthProfileResponse> {
  return authService.createAuthProfile(payload);
}
