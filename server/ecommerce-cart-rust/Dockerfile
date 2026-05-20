FROM rust:1.77-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main(){}" > src/main.rs && cargo build --release 2>/dev/null || true
COPY src/ src/
RUN cargo build --release

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
WORKDIR /app
COPY --from=builder /app/target/release/ecommerce-cart .
EXPOSE 8102
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:8102/health || exit 1
ENTRYPOINT ["/app/ecommerce-cart"]
