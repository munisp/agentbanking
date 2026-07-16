module github.com/remittance-platform/api-gateway

go 1.21

require github.com/gorilla/mux v1.8.0

require (
	go.opentelemetry.io/otel v1.26.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.26.0
	go.opentelemetry.io/otel/sdk v1.26.0
	go.opentelemetry.io/otel/semconv/v1.26.0 v1.26.0
	go.opentelemetry.io/otel/trace v1.26.0
	golang.org/x/time v0.5.0
)
