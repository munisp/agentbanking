FROM golang:1.21-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git gcc musl-dev

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=1 GOOS=linux go build -a -o chart-of-accounts-service .

FROM alpine:3.19

RUN apk --no-cache add ca-certificates curl libc6-compat

WORKDIR /app

COPY --from=builder /app/chart-of-accounts-service .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

USER nobody

ENTRYPOINT ["./chart-of-accounts-service"]
