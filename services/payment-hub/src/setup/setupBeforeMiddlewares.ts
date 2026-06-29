import { type Application } from "express";
import morgan_config from "../config/morgan.config";
import record_request from "../middlewares/recordRequest";

export default function setupBeforeMiddlewares(app: Application): void {
  app.use(morgan_config);
  app.use(record_request);
}
