import express from "express";
import * as controllers from "../controllers";

const router = express.Router();

router.route("/party-lookup-response").put(controllers.send_party_res_to_mojaloop);

export default router;
