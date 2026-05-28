/**
 * Query Tracker Middleware — detects N+1 queries and slow queries.
 *
 * Tracks DB query count per request and logs warnings when:
 *  - A single request makes > 10 DB queries (N+1 pattern)
 *  - A single query takes > 500ms (slow query)
 *
 * Also exposes metrics for the platform health dashboard.
 */

import type { Request, Response, NextFunction } from "express";

interface QueryRecord {
  path: string;
  queryCount: number;
  totalMs: number;
  slowQueries: number;
  timestamp: number;
}

const N_PLUS_ONE_THRESHOLD = 10;
const SLOW_QUERY_MS = 500;
const MAX_HISTORY = 500;

const recentRequests: QueryRecord[] = [];
const nPlusOneAlerts: QueryRecord[] = [];
const slowQueryAlerts: {
  query: string;
  durationMs: number;
  path: string;
  timestamp: number;
}[] = [];

let totalQueries = 0;
let totalSlowQueries = 0;
let totalNPlusOne = 0;

export function getQueryMetrics() {
  return {
    totalQueries,
    totalSlowQueries,
    totalNPlusOne,
    recentNPlusOne: nPlusOneAlerts.slice(-20),
    recentSlowQueries: slowQueryAlerts.slice(-20),
    avgQueriesPerRequest:
      recentRequests.length > 0
        ? recentRequests.reduce((s, r) => s + r.queryCount, 0) /
          recentRequests.length
        : 0,
  };
}

export function trackQuery(
  path: string,
  durationMs: number,
  queryText?: string
) {
  totalQueries++;

  if (durationMs > SLOW_QUERY_MS) {
    totalSlowQueries++;
    slowQueryAlerts.push({
      query: queryText?.slice(0, 200) ?? "unknown",
      durationMs,
      path,
      timestamp: Date.now(),
    });
    if (slowQueryAlerts.length > MAX_HISTORY) slowQueryAlerts.shift();
    console.warn(
      `[SlowQuery] ${durationMs}ms on ${path}: ${queryText?.slice(0, 100) ?? "?"}`
    );
  }
}

export function queryTrackerMiddleware() {
  return (req: Request, res: Response, next: NextFunction) => {
    const path = req.path;
    const start = Date.now();
    let queryCount = 0;

    // Attach tracker to request for instrumentation
    (req as any)._queryTracker = {
      track(durationMs: number, queryText?: string) {
        queryCount++;
        trackQuery(path, durationMs, queryText);
      },
    };

    const originalEnd = res.end.bind(res);
    (res as any).end = function (...args: any[]) {
      const totalMs = Date.now() - start;

      const record: QueryRecord = {
        path,
        queryCount,
        totalMs,
        slowQueries: 0,
        timestamp: Date.now(),
      };

      recentRequests.push(record);
      if (recentRequests.length > MAX_HISTORY) recentRequests.shift();

      if (queryCount > N_PLUS_ONE_THRESHOLD) {
        totalNPlusOne++;
        nPlusOneAlerts.push(record);
        if (nPlusOneAlerts.length > MAX_HISTORY) nPlusOneAlerts.shift();
        console.warn(`[N+1] ${queryCount} queries on ${path} (${totalMs}ms)`);
      }

      return originalEnd(...args);
    };

    next();
  };
}
