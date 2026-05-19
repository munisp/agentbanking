FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o app .
FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /app/app /usr/local/bin/app
EXPOSE 9010
CMD ["app"]
