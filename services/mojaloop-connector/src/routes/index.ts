import express from "express";
import participantRoutes from "./participants";
import partiesRoute from "./parties";
import mojaloopOutboundRoutes from "./mojaloop";
import quotesRoute from "./qoutes";
import transferRoutes from "./transfers";
import ApiError from "../utils/ApiError";
import httpStatus from "http-status";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

const router = express.Router();

router.use("/participants", participantRoutes);
router.use("/parties", partiesRoute);
router.use("/mojaloop", mojaloopOutboundRoutes);
router.use("/quotes", quotesRoute);
router.use("/transfers", transferRoutes);

router.use((req, _) => {
  logger.error("Requested route was not found", req.url);
  throw new ApiError(httpStatus.NOT_FOUND, "Route not found");
});

export default router;
