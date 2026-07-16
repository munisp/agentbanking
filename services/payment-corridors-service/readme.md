# payment-corridor

A high-throughput Rust microservice that selects the optimal payment rail
(CIPS, PAPSS, or SWIFT) for a given remittance instruction.

## Rail priority

| Priority | Rail  | Condition                                     |
| -------- | ----- | --------------------------------------------- |
| 1        | CIPS  | Currency is CNY (configurable)                |
| 2        | PAPSS | Both origin and destination are PAPSS members |
| 3        | SWIFT | Universal fallback                            |

## Running locally

```bash
# with cargo
RUST_LOG=payment_corridor=debug cargo run

# with Docker
docker build -t payment-corridor .
docker run -p 50051:50051 -p 9090:9090 payment-corridor
```

## Configuration

All settings can be overridden via environment variables using the
`CORRIDOR__` prefix and `__` as separator:

```bash
CORRIDOR__SERVER__PORT=50052
CORRIDOR__RAILS__CIPS__CURRENCIES=CNY,HKD
```

Or via `config/default.toml`.

## gRPC interface

```protobuf
service CorridorService {
  rpc SelectRail  (RouteRequest)  returns (RouteResponse);
  rpc HealthCheck (HealthRequest) returns (HealthResponse);
}
```

See `proto/corridor.proto` for the full interface definition.

## Calling from Python

```python
import grpc
from corridor_pb2       import RouteRequest
from corridor_pb2_grpc  import CorridorServiceStub

channel = grpc.insecure_channel("localhost:50051")
stub    = CorridorServiceStub(channel)

response = stub.SelectRail(RouteRequest(
    transaction_id  = "txn-abc-123",
    currency        = "NGN",
    origin_country  = "NG",
    dest_country    = "GH",
    origin_bank_bic = "GTBINGLA",
    dest_bank_bic   = "SCBLGHAC",
    amount_minor    = "500000",
    sender_id       = "sender-uuid",
    beneficiary_id  = "bene-uuid",
))

print(response.selected_rail)   # RAIL_PAPSS
print(response.estimated_ttl_s) # 120
print(response.reason)
```

Generate Python stubs from the proto:

```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=. \
  --grpc_python_out=. \
  proto/corridor.proto
```

## Metrics

Prometheus metrics are exposed on `:9090/metrics`.

Key metric: `corridor_routing_total{rail="Cips|Papss|Swift"}`

## Running tests

```bash
cargo test
```
