# TigerBeetle High-Throughput Configuration

TigerBeetle is designed from the ground up for millions of financial TPS.
Unlike traditional databases, its configuration is mostly compile-time / CLI flags.

## Cluster Topology (Production)

```
6-node cluster: 3 primary + 3 standby (VSR consensus)
Each node: 4 vCPU / 16 GB RAM / NVMe SSD (dedicated)
```

## Key Performance Characteristics

- **10M+ transfers/sec** per cluster (batched)
- **Zero-copy I/O**: Direct NVMe access via io_uring (Linux 5.11+)
- **Deterministic execution**: No GC pauses, no JIT, no allocator contention
- **Batch API**: Client batches up to 8,190 events per request

## Startup Flags

```bash
tigerbeetle start \
  --addresses=0.0.0.0:3000,tb-1:3001,tb-2:3002,tb-3:3003,tb-4:3004,tb-5:3005 \
  --replica=0 \
  --replica-count=6 \
  --cluster=0 \
  --cache-grid-blocks=4096 \
  /data/0_0.tigerbeetle
```

### `--cache-grid-blocks`
Controls the in-memory grid cache size. Each block = 64 KiB.
- `4096` blocks = 256 MB (default)
- `65536` blocks = 4 GB (recommended for production)
- `131072` blocks = 8 GB (high-throughput — keeps most data in memory)

## Client-Side Optimization

### Batch Size
Always batch transfers. Single-transfer calls waste ~99% of throughput.

```typescript
// BAD: 1 transfer per call = ~1K TPS
for (const tx of transfers) {
  await client.createTransfers([tx]);
}

// GOOD: batch 8190 per call = ~10M TPS
const BATCH_SIZE = 8190;
for (let i = 0; i < transfers.length; i += BATCH_SIZE) {
  await client.createTransfers(transfers.slice(i, i + BATCH_SIZE));
}
```

### Connection Pooling
TigerBeetle client is thread-safe. Use a single client instance per process.
For multi-process deployments, each process connects to the cluster independently.

```go
// Go: single client, reuse across goroutines
client, _ := tigerbeetle.NewClient(0, []string{"tb-0:3000", "tb-1:3001", "tb-2:3002"}, 32)
defer client.Close()
// 32 = max concurrent requests (max inflight batches)
```

### Lookup Optimization
Use `lookupAccounts` / `lookupTransfers` with batch IDs instead of single lookups.

## Docker Compose (6-node production)

See `docker-compose.cluster-6.yml` in this directory.

## Kernel Tuning (Host)

```bash
# io_uring performance
echo 1048576 > /proc/sys/fs/aio-max-nr
echo 1048576 > /proc/sys/fs/nr_open

# Disable THP (Transparent Huge Pages) — TigerBeetle manages memory directly
echo never > /sys/kernel/mm/transparent_hugepage/enabled

# NVMe scheduler
echo none > /sys/block/nvme0n1/queue/scheduler
echo 1024 > /sys/block/nvme0n1/queue/nr_requests
```
