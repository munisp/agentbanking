// TypeScript enabled — Sprint 96 security audit
import { Request, Response, NextFunction } from "express";
import zlib from "zlib";

/**
 * Response compression middleware supporting gzip and deflate.
 * Brotli requires native bindings — gzip is universally supported.
 *
 * ROUND-8 PERF: this middleware is NO LONGER MOUNTED (see _core/index.ts) —
 * compression() is the single compression layer. This module previously
 * double-compressed responses AND used blocking zlib.gzipSync on the event
 * loop. It is retained for out-of-band use only, with the sync gzip replaced
 * by async zlib.gzip so even accidental use cannot stall the event loop.
 */
export function responseCompressionMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Skip compression for small responses and non-compressible content
  const acceptEncoding = req.headers["accept-encoding"] ?? "";

  if (!acceptEncoding.includes("gzip") && !acceptEncoding.includes("deflate")) {
    return next();
  }

  // Skip for already-compressed content types
  const skipPaths = ["/api/health", "/api/stripe/webhook"];
  if (skipPaths.some(p => req.path.startsWith(p))) {
    return next();
  }

  // Use Node.js built-in compression for JSON responses
  const originalJson = res.json.bind(res);
  res.json = function (body: any) {
    const jsonStr = JSON.stringify(body);

    // Only compress responses > 1KB
    if (jsonStr.length < 1024 || !acceptEncoding.includes("gzip")) {
      return originalJson(body);
    }

    // Async gzip: never block the event loop on the request path.
    zlib.gzip(Buffer.from(jsonStr), (err, compressed) => {
      if (err) {
        originalJson(body);
        return;
      }
      res.setHeader("Content-Encoding", "gzip");
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Content-Length", compressed.length);
      res.end(compressed);
    });
    return res;
  };

  next();
}
