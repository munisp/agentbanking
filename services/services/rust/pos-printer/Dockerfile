FROM rust:1.74-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml Cargo.lock* ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -f target/release/deps/rust_pos_printer*
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/rust-pos-printer .
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD curl -f http://localhost:8099/health || exit 1
CMD ["./rust-pos-printer"]
