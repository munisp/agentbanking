import express from "express";
import { v1 } from "../../controllers";

const router = express.Router();

router.route("/").get(v1.fetch_tenants);
router.route("/register").post(v1.register_participants);

export default router;
