import express from "express";
import { create_quote, quote_error_callback, quote_put_callback } from "../controllers";

const router = express.Router();

router.route("/:quote_id/error").put(quote_error_callback);
router.route("/:quote_id").put(quote_put_callback);
router.route("/").post(create_quote);

export default router;
