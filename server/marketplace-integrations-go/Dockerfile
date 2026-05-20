FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o marketplace-integrations .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
WORKDIR /app
COPY --from=builder /app/marketplace-integrations .
EXPOSE 8201
HEALTHCHECK --interval=10s --timeout=3s CMD wget -qO- http://localhost:8201/health || exit 1
CMD ["./marketplace-integrations"]
