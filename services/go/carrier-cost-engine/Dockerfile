FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /service .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /service /service
EXPOSE 8080
CMD ["/service"]
