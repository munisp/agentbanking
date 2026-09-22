// TypeScript enabled — Sprint 96 security audit
import type { Request } from "express";
import { jwtVerify } from "jose";
import { getAgentById } from "../db";
import type { Agent } from "../../drizzle/schema";
import { getJwtSecret } from "../lib/envValidation";
import { withCacheTyped } from "../lib/cacheAside";

// Round-8 perf: cache the per-request agent lookup for 15s (Redis,
// type-preserving, singleflight). No invalidation hook exists on agent
// writes, so the staleness bound is the TTL: suspension/role/float changes
// take up to 15s to propagate to this middleware. Fail-open to DB on Redis
// errors. NOTE: requireAgent's "Agent not found" case is never cached.
const AGENT_LOOKUP_CACHE_TTL_S = 15;

export interface AgentSession {
  id: number;
  agentCode: string;
  name: string;
  tier: string;
  role: string;
}

export async function getAgentFromCookie(
  req: Request
): Promise<AgentSession | null> {
  const cookieHeader = req.headers.cookie ?? "";
  const match = cookieHeader.match(/agent_session=([^;]+)/);
  if (!match) return null;

  try {
    const secret = new TextEncoder().encode(getJwtSecret());
    const { payload } = await jwtVerify(match[1], secret);
    return {
      id: Number(payload.sub),
      agentCode: payload.agentCode as string,
      name: payload.name as string,
      tier: payload.tier as string,
      role: (payload.role as string) ?? "agent",
    };
  } catch {
    return null;
  }
}

export async function requireAgent(req: Request): Promise<Agent> {
  const session = await getAgentFromCookie(req);
  if (!session) {
    const err = new Error("Agent session required") as any;
    err.code = "UNAUTHORIZED";
    throw err;
  }
  const agent = await withCacheTyped(
    `agent:id:${session.id}`,
    AGENT_LOOKUP_CACHE_TTL_S,
    () => getAgentById(session.id)
  );
  if (!agent) {
    const err = new Error("Agent not found") as any;
    err.code = "NOT_FOUND";
    throw err;
  }
  return agent;
}
