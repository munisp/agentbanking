import { type Request } from "express";

export interface IAppContext {}

declare global {
  namespace Express {
    interface Request {}
  }
}
