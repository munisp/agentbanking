FROM rust:1.78-slim AS builder
RUN apt-get update && apt-get install -y pkg-config libssl-dev cmake && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
COPY src/ src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/fee-splitter-realtime /usr/local/bin/fee-splitter-realtime
EXPOSE 8080
ENTRYPOINT ["fee-splitter-realtime"]
