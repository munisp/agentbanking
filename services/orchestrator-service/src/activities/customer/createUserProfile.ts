import { userService } from "../../services/userService";
import { IUserProfilePayload, IUserProfileResponse } from "../../types/user";

export async function createUserProfile(payload: IUserProfilePayload): Promise<IUserProfileResponse> {
  return userService.createUserProfile(payload);
}
