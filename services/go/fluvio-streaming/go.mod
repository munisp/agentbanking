module fluvio-streaming

go 1.21

require (
	go.opentelemetry.io/otel v1.26.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.26.0
	go.opentelemetry.io/otel/sdk v1.26.0
	go.opentelemetry.io/otel/trace v1.26.0
	golang.org/x/time v0.5.0
	github.com/gin-gonic/gin v1.9.1
	github.com/infinyon/fluvio-client-go v0.14.0
)
