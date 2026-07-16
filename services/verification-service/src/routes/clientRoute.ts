import { Router } from "express";
import { postRegisterClient } from "../controllers/client/postRegisterClient";
import { getClient } from "../controllers/client/getClient";

const router = Router();

router.route("/").post(postRegisterClient);
router.route("/:id").get(getClient);

export default router;
