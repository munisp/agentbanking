import express from "express";
import { v1 } from "../../controllers";

const router = express.Router();

router.route("/lookup").post(v1.lookup_party);

export default router;
