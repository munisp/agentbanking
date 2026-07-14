import { AxiosError } from "axios";
import { ErrorRequestHandler } from "express";
import httpStatus from "http-status";
import logger from "../config/logger.config";
import ApiError from "../utils/ApiError";

export const errorConverter: ErrorRequestHandler = (err, req, res, next) => {
  let error = err;
  if (!(error instanceof ApiError)) {
    if (error instanceof AxiosError && error.response) {
      const statusCode = httpStatus.INTERNAL_SERVER_ERROR;
      const message = error.response.data?.message || error.message;
      error = new ApiError(
        statusCode,
        message,
        false,
        err.stack,
        error.response.data,
      );
    } else {
      const statusCode = error.statusCode
        ? httpStatus.BAD_REQUEST
        : httpStatus.INTERNAL_SERVER_ERROR;

      const message = error.message || httpStatus[statusCode];

      error = new ApiError(statusCode, message, false, err.stack);
    }
  }
  next(error);
};

export const errorHandler: ErrorRequestHandler = (
  err: ApiError,
  req,
  res,
  next,
) => {
  let { statusCode, message, data } = err;

  if (process.env.NODE_ENV === "production" && !err.isOperational) {
    statusCode = httpStatus.INTERNAL_SERVER_ERROR;
    message = httpStatus[httpStatus.INTERNAL_SERVER_ERROR];
  }

  res.locals.errorMessage = err.message;

  const response = {
    code: statusCode,
    message,
    ...(data || {}),
    ...(process.env.NODE_ENV === "development" && { stack: err.stack }),
  };

  if (process.env.NODE_ENV === "development") {
    logger.error(`Return Error To Caller ${JSON.stringify(response)}`);
  }

  logger.error(
    `Request failed method=${req.method} path=${req.originalUrl} status=${statusCode} message=${message} stack=${err.stack || "n/a"}`,
  );

  res.status(statusCode).send(response);
};
