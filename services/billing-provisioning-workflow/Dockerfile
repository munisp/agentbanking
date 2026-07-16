FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /billing-provisioning-workflow .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /billing-provisioning-workflow /usr/local/bin/
ENV TEMPORAL_ADDR=temporal:7233
ENV TIGERBEETLE_ADDR=tigerbeetle:3001
ENV KAFKA_BROKERS=kafka:9092
ENV REDIS_URL=redis://redis:6379
ENV MOJALOOP_URL=http://mojaloop:3000
ENV APISIX_ADMIN_URL=http://apisix:9180
ENV PERMIFY_ADDR=permify:3476
ENV OPENSEARCH_URL=http://opensearch:9200
EXPOSE 8087
CMD ["billing-provisioning-workflow"]
