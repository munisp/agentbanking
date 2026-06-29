import { Request, Response, NextFunction } from "express";
import { PrometheusService } from "../services/prometheus";

const recordRequest = (req: Request, res: Response, next: NextFunction) => {
  res.on("finish", () => {
    PrometheusService.getInstance().recordRequest(req.method, req.path, res.statusCode);
  });
  next();
};

export default recordRequest;
