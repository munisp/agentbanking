import { Application } from "express";
import health_check_routes from "../routes/healthCheckRoute";
import metrics_routes from "../routes/metricsRoute";
import v1_routes from "../routes/v1";
import path from "node:path";

export default function setupRoutes(app: Application): void {
  app.use("/health", health_check_routes);
  app.use("/metrics", metrics_routes);
  app.use("/api/v1", v1_routes);

  // Root route to serve the HTML file
  app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, "..", "index.html"));
  });
}
