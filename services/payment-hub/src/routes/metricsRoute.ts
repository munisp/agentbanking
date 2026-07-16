import express from "express";
import { PrometheusService } from "../services/prometheus";

const router = express.Router();

router.get("/", PrometheusService.getInstance().handleMetricsRequest);

export default router;
