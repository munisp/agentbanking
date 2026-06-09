FROM rust:1.75-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM alpine:3.19
COPY --from=builder /app/target/release/open-banking-api /service
EXPOSE 8231
CMD ["/service"]
