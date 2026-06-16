FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /mfa-service .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /mfa-service /mfa-service
EXPOSE 8081
ENTRYPOINT ["/mfa-service"]
