import { createClient, type Client } from "tigerbeetle-node";
import logger from "./logger.config";

let _client: Client | null = null;

export function initTigerBeetle(): void {
  const addresses = process.env.TIGERBEETLE_ADDRESSES;
  if (!addresses) {
    logger.warn("[TigerBeetle] TIGERBEETLE_ADDRESSES not set — ledger posting disabled");
    return;
  }

  const clusterId = BigInt(process.env.TIGERBEETLE_CLUSTER_ID ?? "0");

  try {
    _client = createClient({
      cluster_id: clusterId,
      replica_addresses: addresses.split(",").map((a) => a.trim()),
    });
    logger.info("[TigerBeetle] Client initialized");
  } catch (err) {
    logger.error("[TigerBeetle] Failed to initialize client — ledger posting disabled", err);
  }
}

export function getTigerBeetleClient(): Client | null {
  return _client;
}
