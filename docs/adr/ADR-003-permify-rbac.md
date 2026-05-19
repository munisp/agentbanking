# ADR-003: Permify for Permission-Based Access Control

**Status:** Accepted  
**Date:** 2025-02-01  
**Deciders:** Security Architecture Team

## Context

The billing engine requires fine-grained, permission-based access control across 8 distinct billing permissions and 4 role tiers (viewer, operator, manager, admin). Traditional role-based checks embedded in application code become difficult to maintain, audit, and evolve as the permission model grows. The platform needs externalized authorization that can be updated without code deployments.

## Decision

We adopt **Permify** as the externalized authorization engine, implementing a relationship-based access control (ReBAC) model for all billing operations. Permify evaluates permissions at request time based on a declarative schema, enabling dynamic role assignments and permission inheritance without code changes.

The 8 billing permissions are: billing:view, billing:create_invoice, billing:approve_refund, billing:manage_rates, billing:run_reconciliation, billing:view_audit, billing:manage_tenants, and billing:admin.

## Consequences

**Positive:** Centralized permission model is auditable and version-controlled. Permission changes don't require code deployments. ReBAC model naturally supports multi-tenant isolation. Integration with Kafka enables real-time permission change propagation.

**Negative:** Network latency for permission checks on every request (mitigated by caching). Additional infrastructure component to operate. Schema evolution requires careful migration planning. Limited tooling compared to more established solutions like OPA/Casbin.
