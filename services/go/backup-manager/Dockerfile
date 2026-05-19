FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o backup-manager .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates postgresql16-client redis
WORKDIR /app
COPY --from=builder /app/backup-manager .
EXPOSE 8146
CMD ["./backup-manager"]
