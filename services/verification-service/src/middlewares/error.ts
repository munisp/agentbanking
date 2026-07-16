import { ErrorRequestHandler } from "express";
import httpStatus from "http-status";
import logger from "../config/logger.config";

export class ApiError extends Error {
  readonly statusCode: number;
  readonly isOperational: boolean;
  readonly code?: string;
  readonly service?: string;

  constructor(
    statusCode: number,
    message: string,
    code?: string,
    service?: string,
    isOperational = true,
    stack?: string,
  ) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.service = service;
    this.isOperational = isOperational;

    if (stack) {
      this.stack = stack;
    } else {
      Error.captureStackTrace(this, this.constructor);
    }

    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export const errorConverter: ErrorRequestHandler = (err, req, res, next) => {
  let error = err;
  if (!(error instanceof ApiError)) {
    const statusCode = err.statusCode || httpStatus.INTERNAL_SERVER_ERROR;
    const message = err.message;
    error = new ApiError(
      statusCode,
      message,
      undefined,
      undefined,
      false,
      err.stack,
    );
  }
  next(error);
};

export const errorHandler: ErrorRequestHandler = (err, req, res, next) => {
  let { statusCode, message, code, service } = err;

  // Always log the actual error for debugging
  logger.error('Actual error details:', {
    message: err.message,
    statusCode: err.statusCode,
    code: err.code,
    service: err.service,
    isOperational: err.isOperational,
    stack: err.stack,
  });

  if (process.env.NODE_ENV === "production" && !err.isOperational) {
    statusCode = httpStatus.INTERNAL_SERVER_ERROR;
    message = httpStatus[httpStatus.INTERNAL_SERVER_ERROR];
  }

  res.locals.errorMessage = err.message;

  const response = {
    detail: {
      message,
      status: "error",
      ...(code && { code }),
      ...(service && { service }),
      ...(process.env.NODE_ENV === "development" && { stack: err.stack }),
    },
  };

  logger.error(JSON.stringify(response));

  res.status(statusCode).send(response);
};

export class NonRetriableApplicationError extends Error {
  constructor(message?: string) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
    this.name = NonRetriableApplicationError.name;
  }
}

export const raiseHttpError = (
  message: string,
  code: string,
  service: string = "verification-service",
  statusCode: number = httpStatus.BAD_REQUEST,
) => {
  return {
    status: "error",
    message: message,
    code: code,
    service: "verification-service",
  };
};
