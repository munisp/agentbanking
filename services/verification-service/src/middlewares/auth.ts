import { NextFunction, Response } from "express";
import httpStatus from "http-status";
import { readEnv } from "../config/readEnv.config";
import { AppDataSource } from "../database/dataSource";
import { ClientEntity } from "../entity/ClientEntity";
import { AuthRequest } from "../types";
import { ApiError, raiseHttpError } from "./error";

export async function authenticateClient(
  req: AuthRequest,
  res: Response,
  next: NextFunction,
) {
  try {
    const clientId = req.headers["x-client-id"];
    const clientSecret = req.headers["x-client-secret"];

    if (typeof clientId != "string" || typeof clientSecret != "string")
      throw new ApiError(
        httpStatus.FORBIDDEN,
        "Invalid client id/secret header.",
        "VER-401-00",
        "verification-service",
      );

    const client = await AppDataSource.manager.findOne(ClientEntity, {
      where: {
        client_id: clientId,
        client_secret: clientSecret,
      },
    });

    if (!client)
      throw new ApiError(
        httpStatus.FORBIDDEN,
        "Incorrect client id/secret.",
        "VER-401-01",
        "verification-service",
      );

    req.client = client;

    next();
  } catch (e: any) {
    const errorDetail = raiseHttpError(e.message || "Forbidden", "VER-401-01");
    return res
      .status(e.statusCode || httpStatus.FORBIDDEN)
      .json({ detail: errorDetail });
  }
}

export async function authenticateKycAgent(
  req: AuthRequest,
  res: Response,
  next: NextFunction,
) {
  try {
    const kycApiKey = req.headers.authorization;
    const expectedApiKey = readEnv("KYC_FLOW_API_KEY");
    const normalizedApiKey =
      typeof kycApiKey === "string"
        ? kycApiKey.startsWith("Api-Key ")
          ? kycApiKey.slice(8)
          : kycApiKey
        : null;

    if (
      !normalizedApiKey ||
      normalizedApiKey !== expectedApiKey
    )
      throw new ApiError(
        httpStatus.FORBIDDEN,
        "Invalid authentication header.",
        "VER-401-03",
        "verification-service",
      );

    next();
  } catch (e: any) {
    const errorDetail = raiseHttpError(e.message || "Forbidden", "VER-401-02");

    return res
      .status(e.statusCode || httpStatus.FORBIDDEN)
      .json({ detail: errorDetail });
  }
}
