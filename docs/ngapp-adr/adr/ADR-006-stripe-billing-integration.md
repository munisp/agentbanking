# ADR-006: Stripe for Payment Processing

**Status:** Accepted  
**Date:** 2025-03-01  
**Deciders:** Product and Engineering Teams

## Context

The billing engine needs a reliable payment processing provider that supports invoice generation, subscription management, multi-currency payments, and webhook-driven lifecycle events. The provider must handle PCI DSS compliance, reducing our security scope.

## Decision

We integrate **Stripe** as the primary payment processor for all billing operations. Stripe handles invoice creation, payment collection, subscription management, and provides webhook events for lifecycle tracking. Our system maintains only Stripe resource IDs locally, fetching detailed payment data from Stripe's API when needed.

Webhook events handled: invoice.paid (mark paid, update ledger), invoice.payment_failed (trigger dunning workflow), invoice.overdue (escalate to collections). Monthly invoice generation is automated via Manus Heartbeat cron at /api/scheduled/monthly-invoices.

## Consequences

**Positive:** PCI DSS compliance handled by Stripe, dramatically reducing our security scope. Mature webhook system provides reliable event delivery. Multi-currency support built-in. Stripe's test mode enables thorough integration testing.

**Negative:** Transaction fees (2.9% + 30c per transaction). Vendor lock-in for payment processing. Stripe's API versioning requires periodic migration. Webhook delivery can have delays during Stripe incidents.
