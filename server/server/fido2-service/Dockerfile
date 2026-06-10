# ── Build stage ──────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o fido2-service .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/fido2-service .
EXPOSE 8083
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD wget -qO- http://localhost:8083/health || exit 1
ENV PORT=8083 \
    FIDO2_RP_ID=54link.ng \
    FIDO2_RP_NAME="54Link POS" \
    FIDO2_ORIGIN=https://54link.ng
CMD ["./fido2-service"]
