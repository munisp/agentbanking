# GeoLibre instrumentation guide

[GeoLibre](https://github.com/opengeos/GeoLibre) is an external, MIT-licensed GIS
application (React/MapLibre web app + Python uvicorn sidecar + Tauri desktop shell)
used alongside the AgentBanking platform. It is **not** in this repository, so nothing
here was delivered as code — this guide is the agreed pattern for instrumenting it so
its telemetry joins the canonical stack (`infra/observability/`, see
[OBSERVABILITY.md](../../OBSERVABILITY.md)).

Target state: GeoLibre browser traces and sidecar traces land in the same collector
(`otel-collector:4318`), carry the same `tenant.id` baggage, and join seamlessly with
`api-server-ts` spans via W3C `traceparent` propagation.

---

## (a) Web app (React / MapLibre)

### Install

```bash
npm install @opentelemetry/api @opentelemetry/sdk-trace-web \
  @opentelemetry/exporter-trace-otlp-http \
  @opentelemetry/context-zone @opentelemetry/instrumentation \
  @opentelemetry/instrumentation-fetch @opentelemetry/instrumentation-document-load \
  @opentelemetry/resources @opentelemetry/semantic-conventions
```

### Setup module (import first in the app entry, before any fetch calls)

```ts
// geolibre-web/src/telemetry.ts
import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-web";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { ZoneContextManager } from "@opentelemetry/context-zone";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { DocumentLoadInstrumentation } from "@opentelemetry/instrumentation-document-load";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";

export function initTelemetry(): void {
  const endpoint = import.meta.env.VITE_OTEL_ENDPOINT; // e.g. http://otel-collector:4318
  if (!endpoint) return; // env-gated, same contract as the platform services

  const provider = new WebTracerProvider({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: "geolibre-web",
      "deployment.environment.name": import.meta.env.MODE,
    }),
    spanProcessors: [
      new BatchSpanProcessor(
        new OTLPTraceExporter({ url: `${endpoint}/v1/traces` })
      ),
    ],
  });

  provider.register({ contextManager: new ZoneContextManager() });

  registerInstrumentations({
    instrumentations: [
      new DocumentLoadInstrumentation(),
      new FetchInstrumentation({
        // Propagate traceparent (and baggage) to platform API calls only;
        // do NOT inject headers into third-party tile servers.
        propagateTraceHeaderCorsUrls: [/api-server/, /localhost:3000/],
      }),
    ],
  });
}
```

`FetchInstrumentation` automatically injects the W3C `traceparent` header into
matching requests, so calls from the map UI into `api-server-ts` appear as child
spans of the browser trace — one continuous trace from click to Postgres.

### CORS note (collector change required)

Browser OTLP/HTTP export is a cross-origin `POST` to the collector, so the
collector's OTLP HTTP receiver must allow the GeoLibre origin. Add to the
`otlp` receiver in `infra/observability/otel/otel-collector-config.yaml`
(and mirror in `k8s/observability/otel-collector.yaml` when deploying to k8s):

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins:
            - "http://localhost:5173"   # GeoLibre dev server
            - "https://geolibre.example.invalid"  # deployed origin — replace
          allowed_headers:
            - "Content-Type"
            - "traceparent"
            - "tracestate"
            - "baggage"
```

Keep the origin list explicit — do not use `*` on a collector that also serves
internal traffic.

---

## (b) Python sidecar (uvicorn / FastAPI)

The sidecar should reuse the platform's shared module pattern
(`services/shared/observability.py`). Because GeoLibre is an external repo, vendor
a copy of that module (it is import-safe and no-ops without an endpoint) or install
the equivalent packages directly:

```bash
pip install opentelemetry-sdk==1.33.1 \
  opentelemetry-exporter-otlp-proto-http==1.33.1 \
  opentelemetry-instrumentation-fastapi==0.54b1 \
  opentelemetry-instrumentation-requests==0.54b1 \
  prometheus-client==0.22.1
```

Minimal wiring, mirroring `init_observability`:

```python
# geolibre-sidecar/main.py
import os
from fastapi import FastAPI

app = FastAPI(title="geolibre-sidecar")

# Preferred: vendored copy of the platform shared module
#   from shared.observability import init_observability
#   init_observability(app, "geolibre-sidecar", service_version="0.1.0")

# Inline equivalent (if the shared module is not vendored):
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    provider = TracerProvider(resource=Resource.create({
        "service.name": "geolibre-sidecar",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    }))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
```

Run uvicorn as usual; no `opentelemetry-instrument` wrapper is needed when
`FastAPIInstrumentor.instrument_app` is called in-process. Set
`OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` in the sidecar's
environment on `54link-network`.

---

## (c) Desktop / Tauri shell

**Out of scope for this round.** The Tauri shell reuses the web bundle, so the
browser instrumentation above covers its renderer process once the OTLP endpoint is
reachable from the desktop environment. Native (Rust) Tauri-backend tracing would
follow the platform's `services/rust/otel-common` pattern (`init_tracing`,
OTLP/tonic to `:4317`) — candidate for a follow-up wave together with the pending
Rust crate wiring.

---

## (d) Tenant attribution

Same contract as every platform service: baggage key `tenant.id`, sourced from the
app's auth context (not from a client-supplied header at the edge of GeoLibre
itself — GeoLibre sits behind the platform gateway, which has already authenticated
the tenant).

- **Web app**: after login / tenant selection, set baggage so every subsequent
  fetch span and propagated header carries it:

  ```ts
  import { context, propagation } from "@opentelemetry/api";

  export function setTenantContext(tenantId: string): void {
    const bag = propagation.createBaggage({ "tenant.id": { value: tenantId } });
    context.with(propagation.setBaggage(context.active(), bag), () => {
      // application bootstrap continues in this context
    });
  }
  ```

- **Python sidecar**: the vendored `TenantContextMiddleware` reads `x-tenant-id`
  from incoming requests (forwarded by the platform gateway) and stamps
  `tenant.id` baggage + span attribute automatically.

With both halves in place, GeoLibre telemetry flows through the collector's
`transform/tenant` processor like any other service: per-tenant dashboards
(`tenant-overview` template var) and per-tenant alerts apply unchanged.
