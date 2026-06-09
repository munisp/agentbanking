FROM rust:1.82-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
COPY src/ src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/fluvio-consumer /usr/local/bin/
ENV FLUVIO_ENDPOINT=localhost:9003
ENV OPENSEARCH_INDEXER_URL=http://opensearch-indexer:8092/index
ENV HEALTH_PORT=8093
EXPOSE 8093
CMD ["fluvio-consumer"]
