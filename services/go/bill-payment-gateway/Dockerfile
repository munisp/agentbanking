FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /bill-payment-gateway .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /bill-payment-gateway /bill-payment-gateway
EXPOSE 8141
CMD ["/bill-payment-gateway"]
