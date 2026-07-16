import { Application } from "express";
import healthCheckRoute from "../routes/healthCheckRoute";
import billingRoutes from "../routes/billingRoutes";
import { requiredHeaders } from "../middlewares/required_headers";

export default function setupRoutes(app: Application): void {
  app.use("/health", healthCheckRoute);
  app.use("/billing", requiredHeaders(["x-tenant-id"]), billingRoutes);
}
