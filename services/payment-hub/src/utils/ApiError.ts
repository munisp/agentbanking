class ApiError extends Error {
  declare statusCode: number;
  declare isOperational: boolean;
  declare data: object | null;

  constructor(
    statusCode: number,
    message: string,
    isOperational = true,
    stack = "",
    data = null
  ) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = isOperational;
    this.data = data;
    if (stack) {
      this.stack = stack;
    } else {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}

export default ApiError;
