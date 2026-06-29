FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -mod=mod -ldflags="-w -s" -o service .

FROM gcr.io/distroless/static:nonroot
WORKDIR /app
COPY --from=builder /app/service .
USER nonroot:nonroot
EXPOSE 8091
ENTRYPOINT ["/app/service"]
