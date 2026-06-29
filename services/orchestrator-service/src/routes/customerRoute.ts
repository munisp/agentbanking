import { Router } from "express";
import { postCreateCustomer } from "../controllers/customer/postCreateCustomer";
import { postKycCallback } from "../controllers/kyc/postKycCallback";

const router = Router();

router.route("/").post(postCreateCustomer);
router.route("/kyc/callback").post(postKycCallback);

export default router;
