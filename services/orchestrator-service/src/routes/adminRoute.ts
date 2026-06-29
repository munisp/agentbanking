import { Router } from "express";
import { postKycCallback } from "../controllers/kyc/postKycCallback";
import { postCreateAdmin } from "../controllers/admin/postCreateAdmin";

const router = Router();

router.route("/").post(postCreateAdmin);
router.route("/kyc/callback").post(postKycCallback);

export default router;
