import { Router } from "express";
import { postCreateTenant } from "../controllers/tenant/postCreateTenant";

const router = Router();

router.route("/create-tenant").post(postCreateTenant);

export default router;
