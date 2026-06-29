import { Application } from "express";
import health_check_routes from "../routes/healthCheckRoute";
import routes from "../routes";

export default function setupRoutes(app: Application): void {
  app.use("/actuator", health_check_routes);
  app.use("/", routes);
}
