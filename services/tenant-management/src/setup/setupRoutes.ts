import { Application } from "express";
import healthCheckRoute from "../routes/healthCheckRoute";
import systemRoutes from "../routes/systemRoutes";
import tenantRoutes from "../routes/tenantRoutes";
import billingRoutes from "../routes/billingRoutes";
import { requiredHeaders } from "../middlewares/required_headers";

export default function setupRoutes(app: Application): void {
  app.use("/health", healthCheckRoute);
  app.use("/system", requiredHeaders(["x-tenant-id"]), systemRoutes);
  app.use("/tenant", tenantRoutes);
  app.use("/billing", requiredHeaders(["x-tenant-id"]), billingRoutes);
}
