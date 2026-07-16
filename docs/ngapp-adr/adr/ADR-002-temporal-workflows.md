# ADR-002: Temporal for Billing Workflows

**Status:** Accepted  
**Date:** 2025-01-20  
**Deciders:** Platform Architecture Team

## Context

Billing provisioning, invoice lifecycle, and dunning workflows require reliable, long-running orchestration with automatic retries, compensation (saga pattern), and visibility into workflow state. Traditional cron jobs and message queue consumers lack the durability guarantees and observability needed for financial workflows that may span hours or days.

## Decision

We adopt **Temporal** as the workflow orchestration engine for all billing-related business processes. Temporal provides durable execution, automatic retries with configurable backoff, saga pattern support for multi-step provisioning, and a built-in UI for workflow visibility.

Key workflows implemented:

- 7-step tenant billing provisioning (validate, create accounts, configure rates, setup Stripe, provision Kafka topics, initialize ledger, activate)
- Invoice lifecycle (generation, delivery, payment tracking, dunning escalation)
- Settlement processing with rollback capabilities

## Consequences

**Positive:** Durable execution survives process crashes and restarts. Built-in saga pattern simplifies rollback logic for multi-step provisioning. Temporal UI provides real-time visibility into workflow state. Activity-level retries with exponential backoff handle transient failures gracefully.

**Negative:** Additional infrastructure dependency (Temporal server cluster). Learning curve for Temporal's programming model. Debugging distributed workflows requires understanding Temporal's event history model. Go SDK is most mature; TypeScript SDK used here has fewer community examples.
