FROM golang:1.23-alpine3.19-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o mdm-compliance-engine ./cmd/main.go

FROM alpine:3.24
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/mdm-compliance-engine .
EXPOSE 8095
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD wget -qO- http://localhost:8095/health || exit 1
CMD ["./mdm-compliance-engine"]
