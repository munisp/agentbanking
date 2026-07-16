import { Router } from "express";
import { v1 } from "../../controllers";

const router = Router();

router.route("/").get(v1.get_notifications);

export default router;
