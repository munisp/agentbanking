import { NextFunction, Request, Response } from "express";
import createLogger from "../config/logger.config";
import httpStatus from "http-status";

const logger = createLogger(__filename.split("/").pop() || "UnknownFile");

export const asyncHandler =
  <T>(fn: (req: Request, res: Response<T>, next: NextFunction) => void) =>
  (req: Request, res: Response, _next: NextFunction) =>
    Promise.resolve(fn(req, res, _next)).catch((err: any) => {
      // Don't send response if headers already sent
      if (res.headersSent) {
        logger.error(`Headers already sent, error not sent to client: ${err?.message}`);
        return;
      }

      const statusCode = err?.statusCode || err?.status || httpStatus.INTERNAL_SERVER_ERROR;

      const message = err?.message || err?.response?.data?.message || "An unexpected error occurred.";

      const response = {
        success: false,
        message,
      };

      logger.error(`Response Error: ${JSON.stringify(response)}`);

      // Ensure Content-Type header is properly set
      res.setHeader("Content-Type", "application/json");
      
      return res.status(statusCode).json(response);
    });
