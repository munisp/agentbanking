import express from "express";

import tenantRoutes from "./tenants";
import transactionRoutes from "./transactions";
import accountRoutes from "./accounts";
import transferRoutes from "./transfers";
import partiesRoute from "./parties";
import cardPaymentRoutes from "./card_payment";
import notificationRoutes from "./notifications";
import jobsRoutes from "./jobs";
import { extract_custom_headers } from "../../middlewares/ExtractCustomHeaders";

const router = express.Router();

router.use("/tenants", tenantRoutes);
router.use("/transactions", transactionRoutes);
router.use("/transfers", extract_custom_headers, transferRoutes);
router.use("/accounts", extract_custom_headers, accountRoutes);
router.use("/parties", extract_custom_headers, partiesRoute);
router.use("/notifications", extract_custom_headers, notificationRoutes);
router.use("/card-payment", extract_custom_headers, cardPaymentRoutes);
router.use("/jobs", jobsRoutes);

export default router;
