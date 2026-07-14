import { Router } from "express";
import { postInitializeVerification } from "../controllers/kyb/postInitializeVerification";
import { authenticateClient } from "../middlewares/auth";

const router = Router();

router.route("/initialize-verification").post(authenticateClient, postInitializeVerification);

export default router;
