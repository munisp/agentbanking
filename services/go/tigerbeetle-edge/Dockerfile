FROM golang:1.23-alpine3.19-alpine AS builder

# Install build dependencies
RUN apk add --no-cache gcc musl-dev sqlite-dev

# Set working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o tigerbeetle-go-edge .

# Final stage
FROM alpine:3.19

# Install runtime dependencies
RUN apk --no-cache add ca-certificates sqlite

# Create app directory
WORKDIR /app

# Create data directory
RUN mkdir -p /data

# Copy binary from builder
COPY --from=builder /app/tigerbeetle-go-edge .

# Expose port
EXPOSE 8031

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD wget --no-verbose --tries=1 --spider http://localhost:8031/health || exit 1

# Run the application
CMD ["./tigerbeetle-go-edge"]
