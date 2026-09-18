module github.com/54agent/pos-shell/services/go/shared/middleware

// go directive bumped 1.22 -> 1.25.0 (round 5): go.opentelemetry.io/otel v1.43.0
// requires a newer Go toolchain than 1.22; 1.25.0 matches gateway-service and
// tigerbeetle-core. Run `go mod tidy` on first build (CI gate enforces).
go 1.25.0

require (
	go.opentelemetry.io/otel v1.43.0
	go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp v1.43.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.43.0
	go.opentelemetry.io/otel/metric v1.43.0
	go.opentelemetry.io/otel/sdk v1.43.0
	go.opentelemetry.io/otel/sdk/metric v1.43.0
	go.opentelemetry.io/otel/semconv/v1.26.0 v1.26.0
	go.opentelemetry.io/otel/trace v1.43.0
	golang.org/x/time v0.5.0
)
