import express from "express";
import { v1 } from "../../controllers";

const router = express.Router();

router.route("/process-payment").post(v1.process_card_payment);

export default router;
