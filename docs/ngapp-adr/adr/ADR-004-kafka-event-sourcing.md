# ADR-004: Kafka for Event Sourcing and Audit Trail

**Status:** Accepted  
**Date:** 2025-02-10  
**Deciders:** Platform Architecture Team

## Context

The billing engine requires an immutable audit trail for all financial operations, with the ability to replay events for reconciliation, debugging, and compliance reporting. Additionally, multiple downstream services need to react to billing events (invoice created, payment received, refund processed) in near real-time.

## Decision

We adopt **Apache Kafka** as the event backbone for billing event sourcing and audit trail. All billing mutations publish events to dedicated Kafka topics, creating an immutable, ordered log of every financial operation. Consumers include the audit trail service, analytics pipeline, notification dispatcher, and reconciliation engine.

Key topics: billing.ledger.entries, billing.invoices.lifecycle, billing.payments.events, billing.audit.trail, billing.tenant.provisioning.

## Consequences

**Positive:** Immutable event log satisfies regulatory audit requirements. Event replay enables point-in-time reconciliation. Decoupled consumers can be added without modifying producers. Kafka's partitioning provides natural tenant isolation.

**Negative:** Eventual consistency between event publication and consumer processing. Kafka cluster requires significant operational expertise. Schema evolution across topics needs careful management (Avro/Protobuf registry). Storage costs grow linearly with retention period.
