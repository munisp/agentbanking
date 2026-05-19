# Sprint 93 — Security Alert Notifications, Role-Based Nav, Network Heatmap

**Date:** 2026-05-16
**Tests:** 14/14 pass
**Items:** 11/11 complete

---

## Feature 1: Security Alert Notification System

### What was built

A multi-channel notification service that dispatches security alerts (ransomware, DDoS, bulk operation violations, data exfiltration) to administrators via push, email, SMS, webhook, and Slack channels.

### Files created/modified

| File                                                | Action  | Description                                                                                                                                                                                                |
| --------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `server/services/securityAlertNotifier.ts`          | Created | Core notification service with severity classification, multi-channel dispatch, escalation rules, quiet hours, delivery tracking                                                                           |
| `server/routers/alertNotifications.ts`              | Created | tRPC router: listPreferences, getPreference, updatePreference, listDeliveryHistory, getDeliveryStats, testAlert, listEscalationRules, updateEscalationRule, listCategories, acknowledgeAlert, resolveAlert |
| `client/src/pages/AlertNotificationPreferences.tsx` | Created | Admin UI: channel toggles (push/email/SMS/webhook/Slack), severity threshold, quiet hours, category filters, delivery history timeline, test alert button                                                  |

### Key capabilities

- **6 alert categories:** ransomware, DDoS, bulk_operation, data_exfiltration, brute_force, unauthorized_access
- **5 delivery channels:** push notification, email, SMS, webhook, Slack
- **Escalation rules:** auto-escalate unacknowledged critical alerts after configurable timeout
- **Quiet hours:** suppress non-critical alerts during off-hours with override for critical
- **Delivery tracking:** full history with status (pending/sent/delivered/failed/bounced)

---

## Feature 2: Role-Based Navigation Filtering

### What was built

Dynamic sidebar navigation filtering in DashboardLayout based on the logged-in user's PBAC role, so each role only sees screens they have permission to access.

### Files created/modified

| File                                        | Action    | Description                                                                                           |
| ------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------- |
| `client/src/lib/roleNavConfig.ts`           | Rewritten | 7-role hierarchy mapping (super_admin → viewer) with route permissions, display names, badge colors   |
| `client/src/components/DashboardLayout.tsx` | Modified  | Injected `filterNavGroupsByRole()` into `filteredGroups` useMemo to filter sidebar items by user role |

### Role hierarchy (7 levels)

1. **Super Admin** — full access to all 400+ routes
2. **Admin** — all except super-admin-only routes (system config, tenant management)
3. **Manager** — operations, analytics, reports, agent management (no system config)
4. **Supervisor** — team oversight, approvals, disputes (no admin panels)
5. **Operator** — day-to-day POS operations, transactions, customers
6. **Agent** — field agent screens only (POS, transactions, float, loyalty)
7. **Viewer** — read-only dashboards and reports

### Key capabilities

- `filterNavGroupsByRole(navGroups, role)` — filters nav groups and items by role permissions
- `canAccessRoute(path, role)` — boolean check for route-level access control
- `getRoleDisplayName(role)` / `getRoleBadgeColor(role)` — UI helpers for role display
- Admin sees all items; agent sees only POS-related screens; viewer sees only dashboards

---

## Feature 3: Network Quality Heatmap

### What was built

An interactive map visualization that aggregates offline queue metrics by geographic region to identify areas with the worst network connectivity, helping prioritize infrastructure investment.

### Files created/modified

| File                                         | Action  | Description                                                                                                                        |
| -------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `server/routers/networkQualityHeatmap.ts`    | Created | tRPC router: getRegionMetrics, getSummary, getEvents, getRegionDetail, getInfrastructureRecommendations                            |
| `client/src/pages/NetworkQualityHeatmap.tsx` | Created | Full-page dashboard with interactive map grid, regional metrics table, connectivity event timeline, infrastructure recommendations |

### Key capabilities

- **Regional aggregation:** groups agent connectivity data by region (Nigerian states: Lagos, Kano, Rivers, etc.)
- **Quality scoring:** composite score (0-100) from latency, packet loss, uptime, sync success rate
- **Color-coded heatmap:** green (good) → yellow (degraded) → red (critical) visualization
- **Connectivity events timeline:** recent outages, degradations, and recoveries with timestamps
- **Infrastructure recommendations:** prioritized suggestions for worst-performing regions (e.g., "Deploy edge cache in Kano", "Add redundant uplink in Borno")
- **Drill-down:** click any region to see per-agent metrics, historical trends, and active incidents

---

## Wiring

- `alertNotifications` and `networkQualityHeatmap` routers added to `server/routers.ts` appRouter
- `/alert-preferences` and `/network-heatmap` routes added to `client/src/App.tsx`
- Both pages lazy-imported and accessible from DashboardLayout sidebar

---

## Test Summary

| Suite                       | Tests  | Status          |
| --------------------------- | ------ | --------------- |
| SecurityAlertNotifier       | 3      | ✅ Pass         |
| alertNotificationsRouter    | 2      | ✅ Pass         |
| roleNavConfig               | 5      | ✅ Pass         |
| networkQualityHeatmapRouter | 2      | ✅ Pass         |
| Router imports              | 2      | ✅ Pass         |
| **Total**                   | **14** | **✅ All pass** |
