FROM rust:1.95-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/pos-middleware-bridge /usr/local/bin/
ENV RUST_LOG=info RUST_BRIDGE_PORT=9100
EXPOSE 9100
CMD ["pos-middleware-bridge"]
