FROM golang:1.22-alpine AS builder
RUN apk add --no-cache gcc musl-dev
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN CGO_ENABLED=1 GOOS=linux go build -o /tb-commission-sidecar ./cmd/sidecar

FROM alpine:3.19
RUN apk add --no-cache ca-certificates sqlite-libs
COPY --from=builder /tb-commission-sidecar /usr/local/bin/tb-commission-sidecar
RUN mkdir -p /var/lib/54link
EXPOSE 8040
CMD ["tb-commission-sidecar"]
