import { NextFunction, Request, Response } from "express";
import httpStatus from "http-status";
import logger from "../config/logger.config";

export const asyncHandler =
  <T>(fn: (req: Request, res: Response<T>, next: NextFunction) => void) =>
  (req: Request, res: Response, _next: NextFunction) =>
    Promise.resolve(fn(req, res, _next)).catch((err: any) => {
      const statusCode = err?.statusCode || err?.status || httpStatus.INTERNAL_SERVER_ERROR;

      const message = err?.message || err?.response?.data?.message || "An unexpected error occurred.";

      const response = {
        success: false,
        message,
      };

      logger.error(`Response Error: ${JSON.stringify(response)}`);

      return res.status(statusCode).json(response);
    });
