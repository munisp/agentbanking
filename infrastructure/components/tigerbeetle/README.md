# TigerBeetle Ledger

Double-entry financial ledger for the 54agent platform. Replaces ad-hoc balance columns with an
ACID-compliant, append-only ledger that handles high-throughput credit/debit operations.

## Account IDs (reserved ranges)

| Range         | Purpose                        |
|---------------|--------------------------------|
| 1000–1999     | Agent float accounts           |
| 2000–2999     | Customer wallet accounts       |
| 3000–3999     | Commission holding accounts    |
| 4000–4999     | Settlement suspense accounts   |
| 5000–5999     | Fee income accounts            |
| 9000–9099     | System control accounts        |

## Ledger codes

| Code | Currency |
|------|----------|
| 566  | NGN      |
| 840  | USD      |

## Deployment (single-node for dev)

```sh
docker run -d --name tigerbeetle \
  -v $(pwd)/data:/data \
  -p 3001:3001 \
  ghcr.io/tigerbeetle/tigerbeetle:0.16.11 \
  start --addresses=0.0.0.0:3001 /data/0_0.tigerbeetle
```

## Deployment (production — 6-node cluster)

Set `TB_ADDRESSES` in your environment to the comma-separated list of node addresses.
Use the Helm chart at `infrastructure/charts/tigerbeetle/` (to be provisioned separately).

## Integration

Services interact with TigerBeetle via the `transaction-ledger` service which wraps the
Node.js TigerBeetle client. Do NOT call TigerBeetle directly from other services.
