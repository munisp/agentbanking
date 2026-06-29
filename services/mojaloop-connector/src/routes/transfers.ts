import express from "express";
import {
  initiate_transfer,
  receive_transfer,
  put_transfer_callback,
  put_transfer_error_callback,
} from "../controllers";

const router = express.Router();

router.route("/initiate").post(initiate_transfer);
router.route("/:transfer_id").put(put_transfer_callback);
router.route("/:transfer_id/error").put(put_transfer_error_callback);
router.route("/").post(receive_transfer); // payee dfsp receives this request to prepare the transfer

export default router;
