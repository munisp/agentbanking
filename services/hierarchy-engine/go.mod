module github.com/remittance-platform/hierarchy-engine

go 1.21

require (
	go.opentelemetry.io/otel v1.26.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.26.0
	go.opentelemetry.io/otel/sdk v1.26.0
	go.opentelemetry.io/otel/semconv/v1.26.0 v1.26.0
	go.opentelemetry.io/otel/trace v1.26.0
	golang.org/x/time v0.5.0
	github.com/go-redis/redis/v8 v8.11.5
	github.com/gorilla/mux v1.8.1
	github.com/lib/pq v1.10.9
	github.com/segmentio/kafka-go v0.4.47
)

