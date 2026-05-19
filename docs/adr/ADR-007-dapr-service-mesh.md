# ADR-007: Dapr as Service Mesh Sidecar

**Status:** Accepted  
**Date:** 2025-03-10  
**Deciders:** Infrastructure Team

## Context

With 370+ microservices written in Go, Rust, Python, and TypeScript, implementing service-to-service communication, state management, pub/sub, and observability consistently across all languages is a significant challenge. Each language has different HTTP clients, serialization libraries, and retry mechanisms.

## Decision

We adopt **Dapr** (Distributed Application Runtime) as the sidecar for all billing microservices. Dapr provides language-agnostic building blocks for service invocation, state management, pub/sub messaging, and distributed tracing via a consistent HTTP/gRPC API.

Each billing service runs with a Dapr sidecar that handles service discovery, retries, circuit breaking, and distributed tracing. This eliminates the need for language-specific client libraries and ensures consistent behavior across Go, Rust, and Python services.

## Consequences

**Positive:** Consistent service communication patterns across all languages. Built-in retry, circuit breaking, and timeout policies. Pluggable component model supports swapping infrastructure (e.g., Redis to Memcached) without code changes. Distributed tracing automatically propagated.

**Negative:** Sidecar adds memory overhead per pod (~50MB). Additional network hop for every service call. Dapr's component model can be opaque when debugging. Version upgrades require coordinated rollout across all sidecars.
