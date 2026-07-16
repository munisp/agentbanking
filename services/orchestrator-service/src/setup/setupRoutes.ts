import { Application } from "express";
import adminRoute from "../routes/adminRoute";
import agentRoute from "../routes/agentRoute";
import customerRoute from "../routes/customerRoute";
import healthCheckRoute from "../routes/healthCheckRoute";
import tenantRoute from "../routes/tenantRoute";

export default function setupRoutes(app: Application): void {
  app.use("/health", healthCheckRoute);
  app.use("/admin", adminRoute);
  app.use("/customer", customerRoute);
  app.use("/agent", agentRoute);
  app.use("/tenant", tenantRoute);
}
