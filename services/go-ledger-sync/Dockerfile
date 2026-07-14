FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o pos-ledger-sync .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates curl
COPY --from=builder /app/pos-ledger-sync /usr/local/bin/
ENV GO_LEDGER_PORT=9200
EXPOSE 9200
CMD ["pos-ledger-sync"]
