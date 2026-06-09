FROM rust:1.75-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM alpine:3.19
COPY --from=builder /app/target/release/pension-micro /service
EXPOSE 8279
CMD ["/service"]
