FROM rust:1.75-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /app/target/release/fund-flow-settlement .
EXPOSE 8251
HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O- http://localhost:8251/health || exit 1
CMD ["./fund-flow-settlement"]
