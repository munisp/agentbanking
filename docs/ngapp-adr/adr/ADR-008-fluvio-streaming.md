# ADR-008: Fluvio for Real-Time Data Streaming

**Status:** Accepted  
**Date:** 2025-03-15  
**Deciders:** Data Engineering Team

## Context

While Kafka handles event sourcing and audit trails, certain billing use cases require lower-latency stream processing with built-in SmartModules for inline data transformation. Real-time fee splitting, transaction enrichment, and billing event correlation need sub-10ms processing latency that Kafka Streams alone cannot guarantee.

## Decision

We adopt **Fluvio** as a complementary streaming platform for real-time billing data processing. Fluvio's SmartModules (WebAssembly-based inline processors) enable data transformation at the stream level without separate consumer applications. The Rust-based `billing-event-processor` and `fee-splitter-realtime` services use Fluvio for hot-path processing.

Fluvio handles: real-time fee splitting across revenue share participants, transaction enrichment with merchant metadata, billing event correlation for dashboard updates, and backup streaming when Kafka partitions are unavailable.

## Consequences

**Positive:** Sub-millisecond processing latency for hot-path billing events. SmartModules reduce the number of separate consumer services needed. Rust-native client provides zero-copy performance. Acts as a resilient backup when Kafka experiences partition loss.

**Negative:** Smaller community and ecosystem compared to Kafka. Fewer monitoring and management tools available. Team must learn WebAssembly for SmartModule development. Dual streaming platform increases operational complexity.
