FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /mojaloop-connector-pos .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /mojaloop-connector-pos /mojaloop-connector-pos
EXPOSE 8143
CMD ["/mojaloop-connector-pos"]
