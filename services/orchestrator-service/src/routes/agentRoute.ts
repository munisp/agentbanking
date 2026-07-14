import { Router } from "express";
import { postAgentKycCallback } from "../controllers/agent/postAgentKycCallback";
import { postCreateAgent } from "../controllers/agent/postCreateAgent";

const router = Router();

router.route("/").post(postCreateAgent);
router.route("/kyc/callback").post(postAgentKycCallback);

export default router;
