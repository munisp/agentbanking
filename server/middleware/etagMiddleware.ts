/**
 * ETag middleware for Express.
 *
 * Generates ETag headers for JSON responses and returns 304 Not Modified
 * when the client sends a matching If-None-Match header.
 * Also adds Cache-Control headers for API GET responses.
 */

import type { Request, Response, NextFunction } from "express";
import crypto from "crypto";

const MUTABLE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

const NO_CACHE_PATHS = new Set([
  "/api/trpc/auth.",
  "/api/sync/push",
  "/api/sync/pull",
  "/api/stripe",
  "/api/oauth",
]);

function shouldSkip(req: Request): boolean {
  if (MUTABLE_METHODS.has(req.method)) return true;
  for (const prefix of NO_CACHE_PATHS) {
    if (req.path.startsWith(prefix)) return true;
  }
  return false;
}

export function etagMiddleware() {
  return (req: Request, res: Response, next: NextFunction) => {
    if (shouldSkip(req)) return next();

    const originalJson = res.json.bind(res);
    res.json = function (body: unknown) {
      const bodyStr = JSON.stringify(body);
      const etag = `"${crypto.createHash("md5").update(bodyStr).digest("hex")}"`;

      res.setHeader("ETag", etag);

      // Add Cache-Control for GET API responses (short-lived, revalidate)
      if (req.method === "GET" && req.path.startsWith("/api/")) {
        res.setHeader(
          "Cache-Control",
          "private, max-age=10, stale-while-revalidate=30"
        );
      }

      const clientETag = req.headers["if-none-match"];
      if (clientETag === etag) {
        res.status(304).end();
        return res;
      }

      return originalJson(body);
    };

    next();
  };
}
