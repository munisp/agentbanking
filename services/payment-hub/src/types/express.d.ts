import { type Request } from "express";
import { AppAmsEnum, AppSwitchEnum } from "../utils/enums";

export interface IAppContext {
  tenant_name: string;
  ams_name: AppAmsEnum;
  switch_name: AppSwitchEnum;
}

declare global {
  namespace Express {
    interface Request {
      context: IAppContext;
    }
  }
}

export interface AuthRequest extends Request {
  context: IAppContext;
}
