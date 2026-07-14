import { Application } from "express";
import swaggerUi from "swagger-ui-express";
import logger from "./logger.config";
import yaml from "yamljs";
import path from "path";

function swaggerDocs(app: Application, baseUrl: string) {
  try {
    const spec = yaml.load(path.join(process.cwd(), "docs", "swagger.yaml"));
    // @ts-ignore
    app.use("/docs", swaggerUi.serve, swaggerUi.setup(spec));
    logger.info(`Documentation available at ${baseUrl}/docs`);
  } catch {
    logger.warn("swagger.yaml not found — /docs endpoint disabled");
  }
}

export default swaggerDocs;
