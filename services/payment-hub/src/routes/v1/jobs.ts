import express from "express";
import { v1 } from "../../controllers";

const router = express.Router();

router.route("/resolve-pending-transactions").post(v1.resolve_pending_transactions);

router.route("/reattempt-required-transactions").post(v1.re_attempt_required_transactions);

export default router;
