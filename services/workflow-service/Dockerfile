FROM golang:1.23-alpine3.19-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o workflow-service main.go

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
WORKDIR /root/

COPY --from=builder /app/workflow-service .

EXPOSE 8083

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD ["./workflow-service"]
