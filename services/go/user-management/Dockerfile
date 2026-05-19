FROM golang:1.23-alpine3.19-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o user-management main.go

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
WORKDIR /root/

COPY --from=builder /app/user-management .

EXPOSE 8082

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD ["./user-management"]
