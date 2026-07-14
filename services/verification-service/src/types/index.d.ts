import express, { type Request } from "express";
import { ClientEntity } from "../entity/ClientEntity";

declare global {
  namespace Express {
    interface Request {
      client?: ClientEntity;
    }
  }
}

declare module "express" {
  export interface Request {
    client?: ClientEntity;
  }
}

export interface AuthRequest extends Request {
  client?: ClientEntity;
}

export type FieldType<T, K extends keyof T> = T[K];
