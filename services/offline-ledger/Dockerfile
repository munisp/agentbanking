FROM rust:1.77-alpine AS builder
WORKDIR /app
RUN apk add --no-cache musl-dev
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /app/target/release/* /usr/local/bin/service
EXPOSE 8070
CMD ["service"]
