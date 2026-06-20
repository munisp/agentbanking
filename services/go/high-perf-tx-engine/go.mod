module github.com/munisp/agentbanking/services/go/high-perf-tx-engine

go 1.22

require (
	github.com/jackc/pgx/v5 v5.7.2
	github.com/redis/go-redis/v9 v9.7.0
	github.com/segmentio/kafka-go v0.4.47
	github.com/tigerbeetle/tigerbeetle-go v0.16.11
	go.opentelemetry.io/otel v1.32.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.32.0
	go.opentelemetry.io/otel/sdk v1.32.0
	go.opentelemetry.io/otel/trace v1.32.0
	go.uber.org/zap v1.27.0
	google.golang.org/grpc v1.69.2
)
