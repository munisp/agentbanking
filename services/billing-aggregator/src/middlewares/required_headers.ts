import { Request, Response, NextFunction } from "express";
import httpStatus from "http-status";

export function requiredHeaders(requiredHeaders: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const missingHeaders = requiredHeaders.filter((header) => !req.headers[header.toLowerCase()]);

    if (missingHeaders.length > 0) {
      return res.status(httpStatus.BAD_REQUEST).json({
        error: `Missing required headers: ${missingHeaders.join(", ")}`,
      });
    }

    next();
  };
}
