# ── Build stage ──────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o ota-service .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/ota-service .
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD wget -qO- http://localhost:8081/health || exit 1
ENV PORT=8081
CMD ["./ota-service"]
