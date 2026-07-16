import express from "express";
import { v1 } from "../../controllers";

const router = express.Router();

router.route("/").post(v1.create_account);
router.route("/sub").post(v1.create_sub_account);

export default router;
