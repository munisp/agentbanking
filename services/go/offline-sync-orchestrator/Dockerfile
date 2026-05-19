FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /offline-sync-orchestrator .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /offline-sync-orchestrator /offline-sync-orchestrator
EXPOSE 8140
CMD ["/offline-sync-orchestrator"]
