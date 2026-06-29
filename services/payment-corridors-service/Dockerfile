# ── Build stage ──────────────────────────────────────────────────────────────
FROM rust:1.77-slim AS builder

RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Cargo.toml build.rs ./
COPY proto/ proto/
COPY src/   src/
COPY config/ config/

RUN cargo build --release

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/payment-corridor .
COPY --from=builder /app/config/ config/

EXPOSE 50051 9090

ENV RUST_LOG=payment_corridor=info

CMD ["./payment-corridor"]