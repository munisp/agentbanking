# ── Build stage ──────────────────────────────────────────────────────────────
FROM rust:1.78-alpine AS builder
RUN apk add --no-cache musl-dev pkgconfig openssl-dev
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
# Cache dependencies by building a dummy main first
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src
COPY src ./src
RUN touch src/main.rs && cargo build --release

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/target/release/i18n-currency .
EXPOSE 8084
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD wget -qO- http://localhost:8084/health || exit 1
ENV PORT=8084
CMD ["./i18n-currency"]
