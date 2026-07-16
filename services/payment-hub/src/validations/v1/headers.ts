import * as z from "zod";
import { AppAmsEnum, AppSwitchEnum } from "../../utils/enums";

export const HeaderSchema = z.object({
  "x-switch-name": z.nativeEnum(AppSwitchEnum),
  "x-tenant-name": z.string().min(2, "Invalid tenant name"),
  "x-ams-name": z.nativeEnum(AppAmsEnum),
});
