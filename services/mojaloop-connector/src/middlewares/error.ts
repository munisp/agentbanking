import httpStatus from "http-status";
import { ErrorRequestHandler } from "express";
import createLogger from "../config/logger.config";
import ApiError from "../utils/ApiError";
import { IMojaloopError } from "../types";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

export const errorConverter: ErrorRequestHandler = (err, _, __, next) => {
  let error = err;
  if (!(error instanceof ApiError)) {
    const statusCode = error.statusCode
      ? httpStatus.BAD_REQUEST
      : httpStatus.INTERNAL_SERVER_ERROR;
    const message = error.message || httpStatus[statusCode];
    error = new ApiError(statusCode, message, false, err.stack);
  }
  next(error);
};

export const errorHandler: ErrorRequestHandler = (err, _, res, __) => {
  let { statusCode, message } = err;
  if (process.env.NODE_ENV === "production" && !err.isOperational) {
    statusCode = httpStatus.INTERNAL_SERVER_ERROR;
    message = httpStatus[httpStatus.INTERNAL_SERVER_ERROR];
  }

  res.locals.errorMessage = err.message;

  const response: IMojaloopError = {
    errorInformation: {
      errorDescription: message,
      errorCode: "5001",
    },
  };

  if (process.env.NODE_ENV === "development") {
    logger.error("Error handler response data: ", response);
    console.log("Error stack", err.stack);
  }

  res.status(statusCode).send(response);
};
