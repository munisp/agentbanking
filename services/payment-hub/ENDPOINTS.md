# Payment Hub API Endpoint Documentation

## Service Overview

This service exposes HTTP endpoints under:

- `/` (root HTML)
- `/health`
- `/metrics`
- `/api/v1/*`

The main route mounts are defined in `src/setup/setupRoutes.ts`.

---

## Request Processing Flow (Global)

Every HTTP request follows this pipeline:

1. `express.json()` parses JSON request bodies.
2. `morgan` request logging middleware runs.
3. `recordRequest` middleware records request metrics (`method`, `path`, `status`) into Prometheus counters on response finish.
4. Route matching executes route-level middleware/controllers.
5. Most controllers are wrapped with `asyncHandler`, which catches thrown errors and returns:
   ```json
   {
     "success": false,
     "message": "..."
   }
   ```
6. Express error middlewares (`errorConverter`, `errorHandler`) are also configured globally.

> Note: For routes using `asyncHandler`, controller-level catch/response behavior is dominant for thrown async errors.

---

## Common Header Contract (for protected v1 route groups)

These route groups require custom headers via `extract_custom_headers` middleware:

- `/api/v1/transfers/*`
- `/api/v1/accounts/*`
- `/api/v1/parties/*`
- `/api/v1/notifications/*`
- `/api/v1/card-payment/*`
- `/api/v1/transactions/wallet/query`

Required headers:

- `x-switch-name` (enum: `mojaloop`, `vfd`, `lux`, etc. based on `AppSwitchEnum`)
- `x-tenant-name` (tenant/DFSP id)
- `x-ams-name` (enum from `AppAmsEnum`)

Middleware behavior:

1. Validates these headers via Zod.
2. Verifies tenant exists (`tenantRepository.repo.existsBy({ dfsp_id })`).
3. Injects request context:
   - `req.context.tenant_name`
   - `req.context.switch_name`
   - `req.context.ams_name`

Some transaction endpoints (below) use a different header: `tenant`.

---

## Endpoint Catalog

## 1) Health & Metrics

### `GET /health/`

**Purpose**
- Basic liveness check.

**Flow**
1. Route handler returns static string.

**Response**
- `200 OK` with body: `"API is healthy"`.

---

### `GET /metrics/`

**Purpose**
- Exposes Prometheus metrics.

**Flow**
1. Uses `PrometheusService.getInstance().handleMetricsRequest`.
2. Sets response content type to Prometheus format.
3. Returns registry metrics (default + custom `http_request_total`).

**Response**
- `200 OK` plain text metrics payload.

---

### `GET /`

**Purpose**
- Serves root HTML (`index.html`) from app directory.

**Flow**
1. `res.sendFile(...)` returns HTML file.

---

## 2) Tenants

Base path: `/api/v1/tenants`

### `GET /api/v1/tenants/`

**Purpose**
- Returns paginated tenant list.

**Query Parameters**
- `page` (optional)
- `limit` (optional)

**Flow**
1. Validates query with `FetchTenantsSchema` + pagination schema.
2. Computes `skip`/`limit` using `getPagination`.
3. Reads tenants from DB via `tenantRepository.paginatedFind`.
4. Selects fields: `id`, `name`, `dfsp_id`; ordered by `created_at DESC`.
5. Returns `{ data, total }`.

**Response**
- `200 OK`
  ```json
  {
    "data": [{ "id": 1, "name": "...", "dfsp_id": "..." }],
    "total": 100
  }
  ```

---

## 3) Transactions

Base path: `/api/v1/transactions`

### `POST /api/v1/transactions/wallet/query`

**Headers**
- Requires `x-switch-name`, `x-tenant-name`, `x-ams-name`.

**Purpose**
- Queries wallet transactions with filters and pagination.

**Body Fields**
- `id_value` (optional, comma-separated values)
- `SearchText` (optional)
- `successful_only` (`"true" | "false"`)
- `retriable_only` (`"true" | "false"`)
- `exclude_charges` (`"true" | "false"`)
- `page`, `limit`, `start_date`, `end_date` (from pagination schema)

**Flow**
1. Ensures AMS is supported (`SUPPORTED_CORE_AMS`).
2. Validates body with `FetchTransactionsSchema`.
3. Builds TypeORM query dynamically:
   - Filters by `id_value` against JSON fields (`payer/payee`) + direction.
   - Applies `SearchText` on `transaction_id`/`reference`.
   - Applies status/charge/retriable filters.
4. Counts distinct `transaction_id`.
5. Fetches distinct transactions, sorts by `created_at DESC`, applies in-memory slice.
6. Returns paginated-style payload.

**Response**
- `200 OK`
  ```json
  {
    "result": [ ...transactions ],
    "totalRows": 123,
    "currentPage": 1,
    "totalPages": 7
  }
  ```

---

### `GET /api/v1/transactions/:transaction_id/records`

**Headers**
- `tenant` (required)

**Purpose**
- Fetches all DB records for a transaction id.

**Flow**
1. Validates `params.transaction_id` + `headers.tenant`.
2. Calls `transactionRepository.fetch_txn_records_by_txn_id(transaction_id, tenant)`.
3. Returns array of transaction rows.

---

### `GET /api/v1/transactions/last`

**Purpose**
- Returns latest successful transaction for one or more `id_value`s before `max_date`.

**Query Parameters**
- `id_value` (required, comma-separated)
- `max_date` (required)

**Flow**
1. Validates query.
2. Builds payer/payee-direction filter using JSONB conditions.
3. Filters to `status=success` and `created_at <= max_date`.
4. Orders by `created_at DESC`, takes one.
5. Returns `{ transaction: Transaction | null }`.

---

### `GET /api/v1/transactions/:transaction_id`

**Headers**
- `tenant` (required)

**Purpose**
- Returns summarized transaction status/details for transaction id.

**Flow**
1. Validates `params.transaction_id` + `headers.tenant`.
2. Loads records via `fetch_txn_records_by_txn_id`.
3. If empty, returns `404 Transaction not found`.
4. Computes response:
   - `status`, `amount`, `tag`
   - `is_intra` (`true` when exactly 2 records)
   - `completed_at` only when status is `success`
5. Returns summary object.

---

### `GET /api/v1/transactions/`

**Purpose**
- Lists transactions with filters.

**Query Parameters**
- `id_value`, `search_text`, `start_date`, `end_date`, `page`, `limit`
- `successful_only`, `retriable_only`, `exclude_charges`

**Flow**
1. Validates query via `FetchTransactionsSchema`.
2. Builds dynamic TypeORM query with same core filter logic as wallet query.
3. Counts distinct transaction ids.
4. Fetches distinct transactions.
5. Sorts in-memory by `created_at DESC`.
6. Returns `{ data, total }`.

**Implementation Note**
- Code calls `.slice(skip, skip + limit)` without assigning the result, so returned `data` may include full sorted set instead of paged subset.

---

## 4) Transfers

Base path: `/api/v1/transfers`

All transfer endpoints require headers:

- `x-switch-name`
- `x-tenant-name`
- `x-ams-name`

### `POST /api/v1/transfers/initiate`

**Purpose**
- Initiates a transfer through the configured switch connector.

**Body (switch-dependent)**
- Mojaloop schema: amount, currency, `from`, `to`, destination, optional note/reference/tag/hold_id.
- VFD schema: source account fields, `toAccount`, `toBank`, amount, remark, optional transferType.

**Flow**
1. Injects `switch_name` from request context into body.
2. Validates body against union schema.
3. Ensures AMS is supported.
4. Dispatches by switch:
   - `mojaloop` → `MojaloopConnectorApiClient.initialize_transfer(...)`
   - `vfd` → `VfdConnectorApiClient.initialize_transfer(...)`
     - If `toBank == "999999"`, forces `transferType = INTRA`.
5. Returns connector response directly.

---

### `POST /api/v1/transfers/fund`

**Purpose**
- Performs manual funding into an account and records transaction locally.

**Body**
- `accountId`
- `amount` `{ currency, amount }`
- `source`
- `reference`
- `transaction_date` (ISO datetime)
- `note` (optional)

**Flow**
1. Ensures AMS supports core operations.
2. Validates body.
3. Calls core banking `manual_fund_account(...)`.
4. Creates local transaction record using `create_from_generic_initiate_event(...)` with:
   - incoming direction
   - tag `MANUAL FUNDING`
   - generated UUID transaction id
   - local transaction id from core response `resourceId`
5. Returns `{ success: true, transaction_id }`.

---

### `POST /api/v1/transfers/reverse`

**Headers**
- Uses `tenant` header (not `x-tenant-name`) for record lookup validation.

**Purpose**
- Submits reversal events for a transaction and emits failure event.

**Body**
- `transaction_id`
- `reason` (optional)

**Flow**
1. Validates `headers.tenant` and body.
2. Fetches all records for `transaction_id` + tenant.
3. For each record with `local_transaction_id`, publishes Dapr topic `reverse_transfer` with payload:
   - `local_transaction_id`, `currency`
   - id info chosen by transaction direction.
4. After publish completion, asynchronously emits `transaction_failed` event.
5. Returns `200` with success message immediately after publish phase.

---

## 5) Accounts

Base path: `/api/v1/accounts`

Requires headers:

- `x-switch-name`
- `x-tenant-name`
- `x-ams-name`

### `POST /api/v1/accounts/`

**Purpose**
- Creates a primary/core account.

**Body (switch-dependent)**
- Common identity/profile fields.
- `switch_name` is not client-driven; middleware context value is injected.

**Flow**
1. Injects switch from context and validates payload union.
2. Verifies AMS support.
3. Switch dispatch:
   - **Mojaloop path**
     1. Create account in core banking.
     2. Register participant on Mojaloop by account id.
   - **VFD path**
     1. Optionally create/reuse VFD wallet (depending on client type and provided account data).
     2. Create account in core banking with external VFD account linkage.
     3. Register account id on Mojaloop for intra transfers.
4. Returns creation result (includes VFD account fields when applicable).

---

### `POST /api/v1/accounts/sub`

**Purpose**
- Creates a sub-account under an existing profile/account context.

**Body (switch-dependent)**
- Similar profile data as primary account + sub-account specifics (`clientId`, `previousAccountNo`, etc.).

**Flow**
1. Injects `switch_name` from context and validates.
2. Verifies AMS support.
3. Switch dispatch:
   - **Mojaloop path**
     1. Create sub-account in core banking.
     2. Register participant in Mojaloop (uses `mobileNo`).
   - **VFD path**
     1. Create VFD sub-wallet from `previousAccountNo`.
     2. Create core sub-account with VFD external account id.
     3. Register account id on Mojaloop.
4. Returns sub-account response (+ VFD account metadata for VFD flow).

---

## 6) Parties

Base path: `/api/v1/parties`

Requires headers:

- `x-switch-name`
- `x-tenant-name`
- `x-ams-name`

### `POST /api/v1/parties/lookup`

**Purpose**
- Resolves beneficiary/party details before transfer.

**Body (switch-dependent)**
- Mojaloop: `destination`, `identifier`, `identifier_type`
- VFD: `transfer_type`, `account_number`, `bank`

**Flow**
1. Injects `switch_name` from context and validates union.
2. Switch dispatch:
   - `mojaloop` → connector `lookup_party(...)` with tenant.
   - `vfd` → connector `lookup_party(...)`.
     - If `bank == "999999"`, forces transfer type to intra.
3. Returns `{ result }`.

---

## 7) Notifications

Base path: `/api/v1/notifications`

Requires headers:

- `x-switch-name`
- `x-tenant-name`
- `x-ams-name`

### `GET /api/v1/notifications/`

**Purpose**
- Fetches switch-specific notifications.

**Query**
- Pass-through query object to connector.

**Flow**
1. Reads `switch_name` from context.
2. If `vfd`: calls `VfdConnectorApiClient.get_notifications(query, tenant)`.
3. If `lux`: calls `LuxConnectorApiClient.get_notifications(query, tenant)`.
4. Otherwise throws `400 Unsupported Ams`.

---

## 8) Card Payment

Base path: `/api/v1/card-payment`

Requires headers:

- `x-switch-name`
- `x-tenant-name`
- `x-ams-name`

### `POST /api/v1/card-payment/process-payment`

**Purpose**
- Processes card payment request in EMV-like payload format.

**Body (key fields)**
- `amount`, `transactionCurrencyCode`, `transactionDate`, `terminalID`, `agentId`
- `cardData`: `pan`, `expiryMonth`, `expiryYear`, `track2`, `pinBlock`
- several optional EMV fields.

**Flow**
1. Validates body against `ProcessCardPaymentSchema`.
2. Reads processor from `req.context.switch_name`.
3. Supported processor path:
   - `lux` → `LuxConnectorApiClient.process_card_payment(payload)`.
4. Returns processor response.
5. Controller has local try/catch:
   - On any error, logs and returns `500` with generic failure message.

---

## 9) Jobs

Base path: `/api/v1/jobs`

> These endpoints immediately return `202 Accepted` and continue processing asynchronously in background.

### `POST /api/v1/jobs/resolve-pending-transactions`

**Purpose**
- Marks stale pending transactions as failed and refreshes hold reservations.

**Flow**
1. Responds `202 { message: "Accepted" }`.
2. Queries transactions where:
   - `status = pending`
   - `created_at` between 24h ago and 1h ago.
3. For each transaction:
   - If it has `hold_id`: release funds then reserve again, save updated hold id.
   - If it has parent `reference`: does same release/re-reserve on parent transaction.
4. Bulk updates found transactions to `status = failed`.

---

### `POST /api/v1/jobs/reattempt-required-transactions`

**Purpose**
- Re-attempts failed transactions that still have reserved funds.

**Flow**
1. Responds `202 { message: "Accepted" }`.
2. Queries transactions where:
   - `status = failed`
   - `hold_id IS NOT NULL`
   - `created_at` within last 3 days.
   - limits to 100 records.
3. For each transaction, calls Mojaloop initiate transfer helper with reconstructed payload.
4. Logs per-transaction failure if retry call fails; loop continues.

---

## Event-Driven Transaction Flow (Related to Endpoints)

Besides HTTP endpoints, this service also subscribes to Dapr pub/sub topics when server starts.

Startup flow:

1. DB initialization.
2. Subscribe to topics via `subscribeToPubsubTopics(daprServer)`.
3. Start Dapr server.

Topics include events such as:

- `quote_initiated`
- `quote_agreed`
- `quote_failed`
- `reserve_transaction`
- `transaction_completed`
- `transaction_failed`
- `update_local_transaction_id`
- `initiate_txn_generic`
- inflow webhook topics (internal/external pubsub)

Why this matters for endpoint flow:

- `/transfers/reverse` publishes pub/sub events (`reverse_transfer`, then `transaction_failed`).
- Some transfer lifecycles are completed asynchronously via topic handlers, not in the initial HTTP request/response cycle.

---

## Error Behavior Summary

- Validation failures: `422` with message from Zod.
- Business-not-found examples (e.g., missing tenant/transaction): typically `404`.
- Unsupported switch/AMS cases: `400`, `501`, or `502` depending on controller path.
- Card payment endpoint returns custom `500` fallback body on processing exceptions.

---

## Full Route List (Quick Reference)

- `GET /`
- `GET /health/`
- `GET /metrics/`
- `GET /api/v1/tenants/`
- `POST /api/v1/transactions/wallet/query`
- `GET /api/v1/transactions/:transaction_id/records`
- `GET /api/v1/transactions/last`
- `GET /api/v1/transactions/:transaction_id`
- `GET /api/v1/transactions/`
- `POST /api/v1/transfers/initiate`
- `POST /api/v1/transfers/fund`
- `POST /api/v1/transfers/reverse`
- `POST /api/v1/accounts/`
- `POST /api/v1/accounts/sub`
- `POST /api/v1/parties/lookup`
- `GET /api/v1/notifications/`
- `POST /api/v1/card-payment/process-payment`
- `POST /api/v1/jobs/resolve-pending-transactions`
- `POST /api/v1/jobs/reattempt-required-transactions`
