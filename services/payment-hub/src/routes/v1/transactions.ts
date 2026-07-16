import express from "express";
import { v1 } from "../../controllers";
import { extract_custom_headers } from "../../middlewares/ExtractCustomHeaders";

const router = express.Router();

router.route("/wallet/query").post(extract_custom_headers, v1.query_wallet_transactions);
router.route("/:transaction_id/records").get(v1.fetch_txn_records_by_txn_id);
router.route("/last").get(v1.fetch_last_transaction);
router.route("/:transaction_id").get(v1.get_transaction_details);
router.route("/").get(v1.fetch_transactions);

export default router;
