import client from "prom-client";
import { Request, Response } from "express";
import logger from "../config/logger.config";

export class PrometheusService {
  private static instance: PrometheusService;
  private static readonly register = new client.Registry();
  private static readonly requestCount = new client.Counter({
    name: "http_request_total",
    help: "Total number of requests",
    labelNames: ["method", "route", "status_code"],
  });

  private constructor() {} // prevent instantiation from outside

  /** Singleton accessor */
  static getInstance(): PrometheusService {
    if (!this.instance) {
      this.instance = new PrometheusService();
      this.initialize();
    }
    return this.instance;
  }

  /** Initialize default metrics and custom metrics */
  private static initialize(): void {
    if ((this as any)._initialized) return;
    (this as any)._initialized = true;

    client.collectDefaultMetrics({ register: this.register });
    this.register.registerMetric(this.requestCount);

    logger.info("Prometheus metrics initialized successfully");
  }

  /** Record a new request */
  recordRequest(method: string, route: string, statusCode: number): void {
    PrometheusService.requestCount.labels(method, route, String(statusCode)).inc();
  }

  /** Expose metrics for Prometheus to scrape */
  async handleMetricsRequest(_: Request, res: Response): Promise<void> {
    res.set("Content-Type", PrometheusService.register.contentType);
    res.end(await PrometheusService.register.metrics());
  }
}
