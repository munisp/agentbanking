"""
Observability utilities for 54Agent Banking Platform

Structured JSON logging, OpenTelemetry tracing/metrics (OTLP HTTP),
W3C tracecontext + baggage propagation with per-tenant attribution,
and Prometheus-scrapable business metrics.

Canonical wiring::

    from shared.observability import init_observability

    app = FastAPI(title="my-service")
    init_observability(app, "my-service", service_version="1.0.0")

Environment variables:
    OTEL_EXPORTER_OTLP_ENDPOINT   Base OTLP HTTP endpoint, e.g. http://otel-collector:4318.
                                  When unset, OTel tracing/metrics are a no-op (Prometheus
                                  /metrics and the tenant middleware are still installed).
    ENVIRONMENT                   Value for the deployment.environment resource attribute.
    PROMETHEUS_METRICS_ENABLED    Set to "false" to disable the /metrics endpoint and
                                  business metric instruments.
    SERVICE_NAME / LOG_LEVEL      Used by setup_logging().

Business metric contract (scraped via Prometheus; shared with Go/TS services and
the platform alert rules — names and label sets must not drift):
    funds_flow_operations_total{operation,service,tenant,status}   Counter
    ledger_imbalance_detected_total{ledger,tenant}                 Counter
    settlement_lag_seconds{tenant}                                 Histogram (1,5,15,60,300,900,3600)
    payments_failed_total{service,tenant,reason}                   Counter

Legacy helpers preserved from the original module: setup_logging(), get_logger(),
MetricsMiddleware, metrics_router (a hand-rolled /metrics router; superseded by the
prometheus_client endpoint installed by init_observability).
"""

import os
import json
import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from contextvars import ContextVar

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_service_name: str = os.getenv("SERVICE_NAME", "unknown")

_req_id_var: ContextVar[str] = ContextVar("obs_request_id", default="-")
_trace_var: ContextVar[str] = ContextVar("obs_trace_id", default="-")

_log = logging.getLogger("shared.observability")

try:  # prometheus_client is required for the business-metric contract.
    from prometheus_client import Counter, Histogram, REGISTRY, generate_latest, CONTENT_TYPE_LATEST
    _PROM_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency installed per-service
    _PROM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Structured logging (preserved from the original module)
# ---------------------------------------------------------------------------

class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": _service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _req_id_var.get("-"),
            "trace_id": _trace_var.get("-"),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("amount", "agent", "user_id", "txn_id", "duration_ms", "status_code", "method", "path"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, default=str)


def setup_logging(service: str = "", level: str = "") -> None:
    global _service_name
    _service_name = service or os.getenv("SERVICE_NAME", "unknown")
    lvl = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(lvl)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Legacy hand-rolled request metrics (preserved from the original module)
# ---------------------------------------------------------------------------

class _Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.request_count: Dict[str, int] = {}
        self.request_errors: Dict[str, int] = {}
        self.request_latency_sum: Dict[str, float] = {}
        self.request_latency_count: Dict[str, int] = {}

    def record(self, method: str, path: str, status: int, duration: float) -> None:
        key = f'{method} {path}'
        with self._lock:
            self.request_count[key] = self.request_count.get(key, 0) + 1
            if status >= 400:
                self.request_errors[key] = self.request_errors.get(key, 0) + 1
            self.request_latency_sum[key] = self.request_latency_sum.get(key, 0.0) + duration
            self.request_latency_count[key] = self.request_latency_count.get(key, 0) + 1

    def prometheus_text(self) -> str:
        lines = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for key, cnt in self.request_count.items():
                method, path = key.split(" ", 1)
                lines.append(f'http_requests_total{{service="{_service_name}",method="{method}",path="{path}"}} {cnt}')

            lines.append("# HELP http_request_errors_total Total HTTP errors")
            lines.append("# TYPE http_request_errors_total counter")
            for key, cnt in self.request_errors.items():
                method, path = key.split(" ", 1)
                lines.append(f'http_request_errors_total{{service="{_service_name}",method="{method}",path="{path}"}} {cnt}')

            lines.append("# HELP http_request_duration_seconds HTTP request latency")
            lines.append("# TYPE http_request_duration_seconds summary")
            for key in self.request_latency_sum:
                method, path = key.split(" ", 1)
                total = self.request_latency_sum[key]
                count = self.request_latency_count[key]
                lines.append(f'http_request_duration_seconds_sum{{service="{_service_name}",method="{method}",path="{path}"}} {total:.6f}')
                lines.append(f'http_request_duration_seconds_count{{service="{_service_name}",method="{method}",path="{path}"}} {count}')
        return "\n".join(lines) + "\n"


_metrics = _Metrics()

metrics_router = APIRouter(tags=["observability"])


@metrics_router.get("/metrics")
async def prometheus_metrics():
    return Response(content=_metrics.prometheus_text(), media_type="text/plain; charset=utf-8")


class MetricsMiddleware(BaseHTTPMiddleware):
    SKIP = {"/health", "/healthz", "/ready", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP:
            return await call_next(request)
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        _metrics.record(request.method, request.url.path, response.status_code, duration)
        _req_id_var.set(getattr(request.state, "request_id", "-"))
        _trace_var.set(getattr(request.state, "trace_id", "-"))
        return response


# ---------------------------------------------------------------------------
# Per-tenant context middleware (baggage + span attribute)
# ---------------------------------------------------------------------------

class TenantContextMiddleware(BaseHTTPMiddleware):
    """Attach the x-tenant-id header to OTel baggage and the active span.

    Works without OTel installed (pass-through) so services can wire it
    unconditionally; baggage propagation activates once the SDK is present.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant = request.headers.get("x-tenant-id", "unknown")
        token = None
        try:
            from opentelemetry import baggage, trace
            from opentelemetry.context import attach, detach

            token = attach(baggage.set_baggage("tenant.id", tenant))
            span = trace.get_current_span()
            if span is not None and span.is_recording():
                span.set_attribute("tenant.id", tenant)
        except ImportError:
            detach = None
        try:
            return await call_next(request)
        finally:
            if token is not None:
                try:
                    detach(token)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Canonical business metrics (Prometheus-scraped; contract shared platform-wide)
# ---------------------------------------------------------------------------

_SETTLEMENT_LAG_BUCKETS = (1, 5, 15, 60, 300, 900, 3600)
_prom_instruments: Dict[str, Any] = {}


def _prom_metric(kind: Any, name: str, documentation: str, labelnames: tuple, **kwargs: Any) -> Any:
    """Create (or re-use, if already registered by another copy of this module)
    a prometheus_client instrument. Returns None when prometheus_client is absent."""
    if not _PROM_AVAILABLE:
        return None
    if name in _prom_instruments:
        return _prom_instruments[name]
    try:
        instrument = kind(name, documentation, list(labelnames), **kwargs)
    except ValueError:
        # Already registered on the default REGISTRY (duplicate module copy).
        instrument = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    _prom_instruments[name] = instrument
    return instrument


def record_funds_flow_operation(operation: str, tenant: str, status: str, service: Optional[str] = None) -> None:
    """Increment funds_flow_operations_total{operation,service,tenant,status}."""
    counter = _prom_metric(
        Counter, "funds_flow_operations_total",
        "Funds-flow operations processed by the platform",
        ("operation", "service", "tenant", "status"),
    )
    if counter is None:
        return
    try:
        counter.labels(
            operation=operation or "unknown",
            service=service or _service_name,
            tenant=tenant or "unknown",
            status=status or "unknown",
        ).inc()
    except Exception:
        pass


def record_payment_failure(tenant: str, reason: str, service: Optional[str] = None) -> None:
    """Increment payments_failed_total{service,tenant,reason}."""
    counter = _prom_metric(
        Counter, "payments_failed_total",
        "Payments that failed processing",
        ("service", "tenant", "reason"),
    )
    if counter is None:
        return
    try:
        counter.labels(
            service=service or _service_name,
            tenant=tenant or "unknown",
            reason=reason or "unknown",
        ).inc()
    except Exception:
        pass


def record_settlement_lag(tenant: str, seconds: float) -> None:
    """Observe settlement_lag_seconds{tenant} (buckets 1,5,15,60,300,900,3600)."""
    histogram = _prom_metric(
        Histogram, "settlement_lag_seconds",
        "Lag between payment execution and settlement completion",
        ("tenant",), buckets=_SETTLEMENT_LAG_BUCKETS,
    )
    if histogram is None:
        return
    try:
        histogram.labels(tenant=tenant or "unknown").observe(max(float(seconds), 0.0))
    except Exception:
        pass


def record_ledger_imbalance(ledger: str, tenant: str) -> None:
    """Increment ledger_imbalance_detected_total{ledger,tenant}."""
    counter = _prom_metric(
        Counter, "ledger_imbalance_detected_total",
        "Ledger imbalances detected by reconciliation",
        ("ledger", "tenant"),
    )
    if counter is None:
        return
    try:
        counter.labels(ledger=ledger or "unknown", tenant=tenant or "unknown").inc()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Canonical one-call wiring
# ---------------------------------------------------------------------------

def _has_metrics_route(app) -> bool:
    return any(getattr(route, "path", None) == "/metrics" for route in getattr(app, "routes", []))


def _install_prometheus_endpoint(app) -> None:
    """Expose the prometheus_client REGISTRY at /metrics (unless one exists)."""
    if _has_metrics_route(app):
        return
    if _PROM_AVAILABLE:
        async def _metrics_endpoint(request: Request):
            return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

        app.add_route("/metrics", _metrics_endpoint, methods=["GET"], include_in_schema=False)
    else:
        async def _metrics_endpoint_fallback(request: Request):
            return Response(content=_metrics.prometheus_text(), media_type="text/plain; charset=utf-8")

        app.add_route("/metrics", _metrics_endpoint_fallback, methods=["GET"], include_in_schema=False)
        _log.warning("prometheus_client not installed; /metrics serves legacy request counters only")


def _init_otel(service_name: str, service_version: str) -> bool:
    """Set up TracerProvider/MeterProvider with OTLP HTTP exporters.

    Returns False (no-op) when OTEL_EXPORTER_OTLP_ENDPOINT is unset or the
    opentelemetry packages are not installed."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        _log.info("OTEL_EXPORTER_OTLP_ENDPOINT not set; OpenTelemetry tracing/metrics disabled")
        return False
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry import propagate
        from opentelemetry.propagators.composite import CompositePropagator
        try:  # opentelemetry-api >= 1.27 renamed the W3C propagator class
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator as _W3CTraceContextPropagator,
            )
        except ImportError:
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextPropagator as _W3CTraceContextPropagator,
            )
        try:  # opentelemetry-api >= 1.27 renamed the baggage propagator class
            from opentelemetry.baggage.propagation import (
                W3CBaggagePropagator as _BaggagePropagator,
            )
        except ImportError:
            from opentelemetry.baggage.propagation import (
                BaggagePropagator as _BaggagePropagator,
            )
    except ImportError:
        _log.warning("opentelemetry packages not installed; tracing/metrics disabled")
        return False

    endpoint = endpoint.rstrip("/")
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=30000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    propagate.set_global_textmap(
        CompositePropagator([_W3CTraceContextPropagator(), _BaggagePropagator()])
    )
    _log.info("OpenTelemetry OTLP export enabled for %s -> %s", service_name, endpoint)
    return True


def _instrument_app(app) -> None:
    """Auto-instrument FastAPI/requests/SQLAlchemy/Redis; each optional per service."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("FastAPI instrumentation skipped: %s", exc)
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("requests instrumentation skipped: %s", exc)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("sqlalchemy instrumentation skipped: %s", exc)
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("redis instrumentation skipped: %s", exc)


def init_observability(app, service_name: str, service_version: str = "0.0.0") -> None:
    """Canonical one-call observability wiring for every Python service.

    Installs the per-tenant middleware and the Prometheus /metrics endpoint
    unconditionally (unless PROMETHEUS_METRICS_ENABLED=false), and enables
    OTel tracing/metrics + auto-instrumentation when OTEL_EXPORTER_OTLP_ENDPOINT
    is configured. Never raises: observability must not break the service.
    """
    global _service_name
    _service_name = service_name or os.getenv("SERVICE_NAME", "unknown")
    try:
        app.add_middleware(TenantContextMiddleware)
        if os.getenv("PROMETHEUS_METRICS_ENABLED", "true").lower() != "false":
            _install_prometheus_endpoint(app)
        if _init_otel(service_name, service_version):
            _instrument_app(app)
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("init_observability partially failed for %s: %s", service_name, exc)
