FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o tigerbeetle-middleware-hub .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /app/tigerbeetle-middleware-hub /usr/local/bin/
EXPOSE 9300
ENTRYPOINT ["tigerbeetle-middleware-hub"]
