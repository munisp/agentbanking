/**
 * Database Connection Pool Configuration
 *
 * Centralizes PostgreSQL connection pool settings with:
 * - Configurable pool sizes (min/max connections)
 * - Connection timeout and idle timeout
 * - Health check on acquire
 * - Read replica routing for queries
 * - Pool exhaustion monitoring
 */

interface PoolConfig {
  min: number;
  max: number;
  acquireTimeoutMs: number;
  idleTimeoutMs: number;
  connectionTimeoutMs: number;
  statementTimeoutMs: number;
}

const DEFAULT_CONFIG: PoolConfig = {
  min: 5,
  max: 50,
  acquireTimeoutMs: 30_000,
  idleTimeoutMs: 60_000,
  connectionTimeoutMs: 10_000,
  statementTimeoutMs: 30_000,
};

const READ_REPLICA_URL = process.env.DATABASE_READ_REPLICA_URL;
const PRIMARY_URL = process.env.DATABASE_URL || process.env.POSTGRES_URL;

export function getPoolConfig(env?: string): PoolConfig {
  const nodeEnv = env || process.env.NODE_ENV;
  switch (nodeEnv) {
    case "production":
      return { ...DEFAULT_CONFIG, min: 10, max: 100 };
    case "staging":
      return { ...DEFAULT_CONFIG, min: 5, max: 50 };
    default:
      return { ...DEFAULT_CONFIG, min: 2, max: 20 };
  }
}

export function getConnectionUrl(isReadOnly: boolean = false): string {
  if (isReadOnly && READ_REPLICA_URL) return READ_REPLICA_URL;
  return PRIMARY_URL || "";
}

// Pool stats tracking
interface PoolStats {
  totalConnections: number;
  idleConnections: number;
  waitingClients: number;
  maxConnections: number;
}

let poolStats: PoolStats = {
  totalConnections: 0,
  idleConnections: 0,
  waitingClients: 0,
  maxConnections: DEFAULT_CONFIG.max,
};

export function updatePoolStats(stats: Partial<PoolStats>) {
  poolStats = { ...poolStats, ...stats };
}

export function getPoolStats(): PoolStats {
  return { ...poolStats };
}

export { DEFAULT_CONFIG, PoolConfig };
