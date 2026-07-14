import express from "express";
import * as controllers from "../controllers";

const router = express.Router();

router.route("/lookup").post(controllers.lookup_party);
router.route("/:identifier_type/:identifier/error").put(controllers.put_party_error);
router.route("/:identifier_type/:identifier").put(controllers.put_lookup_party);

export default router;
