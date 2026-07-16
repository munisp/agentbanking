/**
 * Fluvio Streaming Integration — 54agent Platform
 *
 * Provides TypeScript integration with the Fluvio streaming platform:
 * - Producer: Send events to Fluvio topics via HTTP sidecar
 * - Consumer: Poll events from Fluvio via HTTP sidecar
 * - SmartModule: Manage and deploy WASM SmartModules
 * - Topic management
 */

const FLUVIO_HOST = process.env.FLUVIO_HOST ?? "localhost";
const FLUVIO_HTTP_PORT = parseInt(process.env.FLUVIO_HTTP_PORT ?? "9003");
const FLUVIO_ADMIN_PORT = parseInt(process.env.FLUVIO_ADMIN_PORT ?? "9004");

interface FluvioTopicConfig {
  name: string;
  partitions?: number;
  replicationFactor?: number;
  retentionMs?: number;
}

interface FluvioConsumerConfig {
  topic: string;
  partition?: number;
  offset?: "beginning" | "end" | number;
  maxRecords?: number;
  smartmodule?: string;
}

export class FluvioIntegration {
  private httpUrl: string;
  private adminUrl: string;
  private consumers: Map<
    string,
    { active: boolean; handler: (record: any) => Promise<void> }
  > = new Map();

  constructor() {
    this.httpUrl = `http://${FLUVIO_HOST}:${FLUVIO_HTTP_PORT}`;
    this.adminUrl = `http://${FLUVIO_HOST}:${FLUVIO_ADMIN_PORT}`;
  }

  async produce(
    topic: string,
    key: string,
    value: string | Record<string, unknown>
  ): Promise<boolean> {
    try {
      const record = typeof value === "string" ? value : JSON.stringify(value);
      const res = await fetch(`${this.httpUrl}/produce`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, key, value: record }),
        signal: AbortSignal.timeout(5000),
      });
      return res.ok;
    } catch (err) {
      console.warn(
        `[Fluvio] Produce to ${topic} failed:`,
        (err as Error).message
      );
      return false;
    }
  }

  async produceBatch(
    topic: string,
    records: Array<{ key: string; value: string }>
  ): Promise<boolean> {
    try {
      const res = await fetch(`${this.httpUrl}/produce/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, records }),
        signal: AbortSignal.timeout(10000),
      });
      return res.ok;
    } catch (err) {
      console.warn(
        `[Fluvio] Batch produce to ${topic} failed:`,
        (err as Error).message
      );
      return false;
    }
  }

  async consume(config: FluvioConsumerConfig): Promise<any[]> {
    try {
      const params = new URLSearchParams({
        topic: config.topic,
        ...(config.partition !== undefined
          ? { partition: String(config.partition) }
          : {}),
        ...(config.offset !== undefined
          ? { offset: String(config.offset) }
          : {}),
        ...(config.maxRecords !== undefined
          ? { max_records: String(config.maxRecords) }
          : {}),
        ...(config.smartmodule ? { smartmodule: config.smartmodule } : {}),
      });
      const res = await fetch(`${this.httpUrl}/consume?${params}`, {
        signal: AbortSignal.timeout(10000),
      });
      if (res.ok) return (await res.json()) as any[];
      return [];
    } catch (err) {
      console.warn(
        `[Fluvio] Consume from ${config.topic} failed:`,
        (err as Error).message
      );
      return [];
    }
  }

  async startPollingConsumer(
    topic: string,
    handler: (record: any) => Promise<void>,
    intervalMs: number = 1000
  ): Promise<void> {
    this.consumers.set(topic, { active: true, handler });
    let offset: number | "end" = "end";

    const poll = async () => {
      const consumer = this.consumers.get(topic);
      if (!consumer?.active) return;

      try {
        const records = await this.consume({
          topic,
          offset,
          maxRecords: 100,
        });
        for (const record of records) {
          await consumer.handler(record);
          if (record.offset !== undefined) offset = record.offset + 1;
        }
      } catch (err) {
        console.warn(`[Fluvio] Poll ${topic} error:`, (err as Error).message);
      }

      if (consumer.active) {
        setTimeout(poll, intervalMs);
      }
    };
    poll();
    console.log(`[Fluvio] Polling consumer started for: ${topic}`);
  }

  stopConsumer(topic: string): void {
    const consumer = this.consumers.get(topic);
    if (consumer) {
      consumer.active = false;
      this.consumers.delete(topic);
      console.log(`[Fluvio] Consumer stopped for: ${topic}`);
    }
  }

  async createTopic(config: FluvioTopicConfig): Promise<boolean> {
    try {
      const res = await fetch(`${this.adminUrl}/topics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: config.name,
          partitions: config.partitions ?? 3,
          replication_factor: config.replicationFactor ?? 1,
          retention_time_ms: config.retentionMs ?? 604800000, // 7 days
        }),
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) {
        console.log(`[Fluvio] Topic '${config.name}' created`);
        return true;
      }
      return false;
    } catch (err) {
      console.warn(`[Fluvio] Create topic failed:`, (err as Error).message);
      return false;
    }
  }

  async listTopics(): Promise<string[]> {
    try {
      const res = await fetch(`${this.adminUrl}/topics`, {
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) {
        const data = (await res.json()) as any[];
        return data.map(t => t.name ?? t);
      }
      return [];
    } catch {
      return [];
    }
  }

  async health(): Promise<boolean> {
    try {
      const res = await fetch(`${this.httpUrl}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  getActiveConsumers(): string[] {
    return Array.from(this.consumers.entries())
      .filter(([, v]) => v.active)
      .map(([k]) => k);
  }
}

export const fluvioIntegration = new FluvioIntegration();
