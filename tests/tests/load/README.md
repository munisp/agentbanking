# k6 Load Tests — 54agent POS Shell

## Prerequisites

Install k6: https://k6.io/docs/getting-started/installation/

```bash
# macOS
brew install k6

# Ubuntu/Debian
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

## Scenarios

| File | Description | Targets |
|---|---|---|
| `transaction-throughput.js` | Cash In/Out ramp to 200 VUs | p95 < 500 ms, error rate < 1% |
| `float-topup.js` | Float top-up steady 50 VUs | p95 < 800 ms, error rate < 1% |
| `dispute-creation.js` | Dispute spike to 100 RPS | p95 < 600 ms, error rate < 1% |

## Running

```bash
# Run against local dev server
k6 run tests/load/transaction-throughput.js \
  -e BASE_URL=http://localhost:3000 \
  -e AGENT_CODE=AGT001 \
  -e AGENT_PIN=1234

# Run against staging
k6 run tests/load/transaction-throughput.js \
  -e BASE_URL=https://staging.54agent.com \
  -e AGENT_CODE=AGT001 \
  -e AGENT_PIN=1234

# Run all three scenarios sequentially
for f in tests/load/*.js; do
  k6 run "$f" -e BASE_URL=http://localhost:3000 -e AGENT_CODE=AGT001 -e AGENT_PIN=1234
done
```

## Interpreting Results

k6 outputs a summary table after each run. Key metrics to watch:

- `http_req_duration` — response time (p50, p90, p95, p99)
- `http_req_failed` — percentage of failed requests
- `transaction_errors` / `float_topup_errors` / `dispute_errors` — custom error rates
- `vus` — active virtual users at each point in time

A passing run shows all thresholds in green. Red thresholds indicate the system is not meeting SLAs under load.
