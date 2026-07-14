import { Router } from "express";
import { authenticateClient, authenticateKycAgent } from "../middlewares/auth";
import { postInitializeVerification } from "../controllers/kyc/postInitializeVerification";
import { postVerify } from "../controllers/kyc/postVerify";
import { testCallback } from "../controllers/kyc/testCallback";

const router = Router();

router.route("/initialize-verification").post(authenticateClient, postInitializeVerification);
router.route("/verify").post(authenticateKycAgent, postVerify);
router.route("/test-callback").post(testCallback);

export default router;
