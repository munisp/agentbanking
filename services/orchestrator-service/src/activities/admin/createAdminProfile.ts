import { adminService } from "../../services/adminService";
import { IAdminProfilePayload } from "../../types/admin";

export async function createAdminProfile(payload: IAdminProfilePayload) {
  await adminService.createAdminProfile(payload);
}
