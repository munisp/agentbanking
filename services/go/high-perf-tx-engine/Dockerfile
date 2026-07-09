FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /tx-engine .

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /tx-engine /tx-engine
EXPOSE 8300
USER nonroot:nonroot
ENTRYPOINT ["/tx-engine"]
