import express from "express";
import * as controllers from "../controllers";

const router = express.Router();

router.route("/register").post(controllers.register_participant);
router.route("/lookup").post(controllers.lookup_participants);
router.route("/:identifier_type/:identifier/error").put(controllers.put_participant_error);
router.route("/:identifier_type/:identifier").put(controllers.put_participant); // callback

export default router;
