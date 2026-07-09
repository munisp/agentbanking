FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o fund-flow-engine .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /app/fund-flow-engine .
EXPOSE 8250
HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O- http://localhost:8250/health || exit 1
CMD ["./fund-flow-engine"]
