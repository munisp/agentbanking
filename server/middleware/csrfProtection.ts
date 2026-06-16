/**
 * CSRF Protection — Double-Submit Cookie Pattern
 *
 * - Sets a random CSRF token in a cookie on every response
 * - Requires the token in the X-CSRF-Token header on mutations
 * - Skips CSRF check for: health endpoints, webhooks, API key auth
 */
import crypto from "crypto";
import type { Request, Response, NextFunction } from "express";

const CSRF_COOKIE = "csrf_token";
const CSRF_HEADER = "x-csrf-token";
const TOKEN_LENGTH = 32;

const SKIP_PATHS = ["/health", "/api/webhooks", "/api/v1/webhooks", "/trpc"];
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function generateCsrfToken(): string {
  return crypto.randomBytes(TOKEN_LENGTH).toString("hex");
}

export function csrfMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Set CSRF cookie if not present
  if (!req.cookies?.[CSRF_COOKIE]) {
    const token = generateCsrfToken();
    res.cookie(CSRF_COOKIE, token, {
      httpOnly: false, // Must be readable by JS
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 24 * 60 * 60 * 1000, // 24 hours
    });
  }

  // Skip CSRF check for safe methods
  if (SAFE_METHODS.has(req.method)) return next();

  // Skip CSRF check for whitelisted paths
  if (SKIP_PATHS.some(p => req.path.startsWith(p))) return next();

  // Skip if API key auth is present (service-to-service)
  if (req.headers["x-api-key"]) return next();

  // Validate CSRF token
  const cookieToken = req.cookies?.[CSRF_COOKIE];
  const headerToken = req.headers[CSRF_HEADER];

  if (!cookieToken || !headerToken || cookieToken !== headerToken) {
    res.status(403).json({ error: "CSRF token validation failed" });
    return;
  }

  next();
}
