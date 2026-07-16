import { type Application } from "express";
import { errorConverter, errorHandler } from "../middlewares/error";

export default function setupAfterMiddlewares(app: Application): void {
  app.use(errorConverter);
  app.use(errorHandler);
}
