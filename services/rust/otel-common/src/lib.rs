//! otel-common — shared OpenTelemetry wiring for 54Link Rust services (Wave-4).
//!
//! Provides:
//! - `init_tracing`: env-gated OTLP tracing setup (falls back to fmt-only when
//!   `OTEL_EXPORTER_OTLP_ENDPOINT` is unset).
//! - `tenant_id_from_headers` / `record_tenant_span_attr`: tenant propagation.
//! - `metrics_handle`: Prometheus text exposition of the default registry.
//! - `register_business_metrics` + recorders for the cross-language contract
//!   counters `funds_flow_operations_total` and `payments_failed_total`.

use opentelemetry::{global, trace::TracerProvider as _, KeyValue};
use opentelemetry_otlp::SpanExporter;
use opentelemetry_sdk::{trace::SdkTracerProvider, Resource};
use prometheus::{IntCounterVec, Opts};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// Guard that shuts the tracer provider down cleanly on drop.
/// Keep this alive for the lifetime of `main`.
pub struct OtelGuard {
    provider: Option<SdkTracerProvider>,
}

impl Drop for OtelGuard {
    fn drop(&mut self) {
        if let Some(provider) = self.provider.take() {
            if let Err(e) = provider.shutdown() {
                eprintln!("[otel-common] tracer provider shutdown error: {:?}", e);
            }
        }
    }
}

/// Initialize tracing for a service.
///
/// - If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, installs a global tracer provider
///   with an OTLP/tonic span exporter, W3C trace-context propagator, and a
///   tracing subscriber stack of EnvFilter + fmt + OpenTelemetryLayer.
/// - If unset, installs EnvFilter + fmt only and logs one line.
///
/// Resource attributes: `service.name`, `service.version` (CARGO_PKG_VERSION of
/// the calling crate is not visible here, so falls back to `OTEL_SERVICE_VERSION`
/// or "unknown"), `deployment.environment` (`ENVIRONMENT` env, default
/// "production").
pub fn init_tracing(
    service_name: &'static str,
) -> Result<OtelGuard, Box<dyn std::error::Error + Send + Sync>> {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));

    let endpoint = match std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
        Ok(ep) if !ep.trim().is_empty() => ep,
        _ => {
            tracing_subscriber::registry()
                .with(filter)
                .with(tracing_subscriber::fmt::layer())
                .init();
            tracing::info!(
                service = service_name,
                "OTEL_EXPORTER_OTLP_ENDPOINT unset; fmt-only logging, OTLP export disabled"
            );
            return Ok(OtelGuard { provider: None });
        }
    };

    global::set_text_map_propagator(opentelemetry_sdk::propagation::TraceContextPropagator::new());

    let environment =
        std::env::var("ENVIRONMENT").unwrap_or_else(|_| "production".to_string());
    let service_version =
        std::env::var("OTEL_SERVICE_VERSION").unwrap_or_else(|_| "unknown".to_string());

    let resource = Resource::builder()
        .with_service_name(service_name)
        .with_attributes([
            KeyValue::new(
                opentelemetry_semantic_conventions::resource::SERVICE_VERSION,
                service_version,
            ),
            KeyValue::new(
                opentelemetry_semantic_conventions::resource::DEPLOYMENT_ENVIRONMENT,
                environment,
            ),
        ])
        .build();

    let exporter = SpanExporter::builder()
        .with_tonic()
        .with_endpoint(endpoint)
        .build()?;

    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_batch_exporter(exporter)
        .build();

    let tracer = provider.tracer(service_name);
    global::set_tracer_provider(provider.clone());

    let otel_layer = tracing_opentelemetry::OpenTelemetryLayer::new(tracer);

    tracing_subscriber::registry()
        .with(filter)
        .with(tracing_subscriber::fmt::layer())
        .with(otel_layer)
        .init();

    tracing::info!(service = service_name, "OTel tracing initialized (OTLP/tonic)");

    Ok(OtelGuard {
        provider: Some(provider),
    })
}

/// Extract tenant id from the `x-tenant-id` header; defaults to "unknown".
pub fn tenant_id_from_headers(headers: &http::HeaderMap) -> String {
    headers
        .get("x-tenant-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .unwrap_or_else(|| "unknown".to_string())
}

/// Stamp `tenant.id` on the current tracing span.
pub fn record_tenant_span_attr(tenant: &str) {
    tracing::Span::current().record("tenant.id", tenant);
}

/// Render the Prometheus default registry to exposition text (for `/metrics`).
pub fn metrics_handle() -> String {
    let encoder = prometheus::TextEncoder::new();
    let metric_families = prometheus::default_registry().gather();
    encoder
        .encode_to_string(&metric_families)
        .unwrap_or_else(|e| format!("# metrics encode error: {}\n", e))
}

// ── Canonical cross-language business metrics ─────────────────────────────────

static FUNDS_FLOW_OPERATIONS: once_cell::sync::Lazy<IntCounterVec> = once_cell::sync::Lazy::new(|| {
    let counter = IntCounterVec::new(
        Opts::new(
            "funds_flow_operations_total",
            "Total funds-flow operations processed (cross-language contract)",
        ),
        &["operation", "service", "tenant", "status"],
    )
    .expect("funds_flow_operations_total must be a valid counter");
    prometheus::default_registry()
        .register(Box::new(counter.clone()))
        .expect("funds_flow_operations_total registration must succeed");
    counter
});

static PAYMENTS_FAILED: once_cell::sync::Lazy<IntCounterVec> = once_cell::sync::Lazy::new(|| {
    let counter = IntCounterVec::new(
        Opts::new(
            "payments_failed_total",
            "Total failed payment operations (cross-language contract)",
        ),
        &["service", "tenant", "reason"],
    )
    .expect("payments_failed_total must be a valid counter");
    prometheus::default_registry()
        .register(Box::new(counter.clone()))
        .expect("payments_failed_total registration must succeed");
    counter
});

/// Eagerly register the canonical business counters with the default registry.
pub fn register_business_metrics() {
    once_cell::sync::Lazy::force(&FUNDS_FLOW_OPERATIONS);
    once_cell::sync::Lazy::force(&PAYMENTS_FAILED);
}

/// Increment `funds_flow_operations_total{operation,service,tenant,status}`.
pub fn record_funds_flow_operation(operation: &str, service: &str, tenant: &str, status: &str) {
    FUNDS_FLOW_OPERATIONS
        .with_label_values(&[operation, service, tenant, status])
        .inc();
}

/// Increment `payments_failed_total{service,tenant,reason}`.
pub fn record_payment_failed(service: &str, tenant: &str, reason: &str) {
    PAYMENTS_FAILED
        .with_label_values(&[service, tenant, reason])
        .inc();
}
