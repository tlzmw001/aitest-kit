# Discount System Public API Document

This document describes the external behavior of the `discount_system` service. It is intended for consumers and test designers. It does not describe implementation internals.

## Overview

`discount_system` evaluates discount eligibility for an item purchase request and returns a deterministic discount decision. A successful decision can also be queried later by `request_id`.

## Service Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/discount/policy` | Evaluate discount policy |
| `GET` | `/api/v1/discount/decisions/{request_id}` | Query a stored decision |
| `DELETE` | `/api/v1/discount/decisions/{request_id}` | Delete a stored decision for cleanup |

## Health Check

### `GET /health`

Successful response:

```json
{
  "status": "ok"
}
```

## Evaluate Discount Policy

### `POST /api/v1/discount/policy`

Request body:

```json
{
  "user_id": "u_001",
  "user_level": "normal",
  "item_id": "item_001",
  "item_price": 120.5,
  "scene": "checkout",
  "stock": 5,
  "request_id": "req_001"
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | yes | User identifier |
| `user_level` | string | yes | User level. Allowed values: `normal`, `vip`, `black` |
| `item_id` | string | yes | Item identifier |
| `item_price` | number | yes | Item price. Must be greater than or equal to 0 |
| `scene` | string | yes | Business scene. Allowed values: `checkout`, `campaign`, `fallback` |
| `stock` | integer | yes | Available stock. Must be greater than or equal to 0 |
| `request_id` | string | yes | Request identifier |

Successful response:

```json
{
  "code": 0,
  "eligible": true,
  "discount_rate": 0.9,
  "reason_code": "VIP_CHECKOUT",
  "request_id": "req_001"
}
```

Response fields:

| Field | Type | Description |
|---|---|---|
| `code` | integer | Business code. `0` means the request was evaluated successfully |
| `eligible` | boolean | Whether the user is eligible for a discount |
| `discount_rate` | number | Applied discount rate |
| `reason_code` | string | Decision reason |
| `request_id` | string | Echoed request identifier |

Validation errors use the HTTP framework's standard validation error format.

## Business Rules

Rules are evaluated by priority. A higher-priority rule wins when multiple conditions match.

| Priority | Rule | Condition | Decision |
|---|---|---|---|
| 1 | Blocked user | `user_level = black` | `eligible=false`, `discount_rate=1.0`, `reason_code=USER_BLOCKED` |
| 2 | Empty stock | `stock = 0` | `eligible=false`, `discount_rate=1.0`, `reason_code=STOCK_EMPTY` |
| 3 | Campaign | `scene = campaign` and `stock > 0` | `eligible=true`, `discount_rate=0.8`, `reason_code=CAMPAIGN` |
| 4 | VIP checkout | `user_level = vip` and `scene = checkout` and `stock > 0` | `eligible=true`, `discount_rate=0.9`, `reason_code=VIP_CHECKOUT` |
| 5 | Default | No earlier rule matched | `eligible=true`, `discount_rate=1.0`, `reason_code=DEFAULT` |

## Query Stored Decision

### `GET /api/v1/discount/decisions/{request_id}`

Successful response when found:

```json
{
  "found": true,
  "request_id": "req_001",
  "decision": {
    "code": 0,
    "eligible": true,
    "discount_rate": 0.9,
    "reason_code": "VIP_CHECKOUT",
    "request_id": "req_001"
  }
}
```

Response when not found:

```json
{
  "found": false,
  "request_id": "req_missing",
  "error": "DECISION_NOT_FOUND"
}
```

The not-found response uses HTTP `404`.

## Delete Stored Decision

### `DELETE /api/v1/discount/decisions/{request_id}`

Response:

```json
{
  "deleted": true,
  "request_id": "req_001"
}
```

If the decision does not exist, the endpoint still returns success with `deleted=false`.

## Notes For Test Designers

- Successful policy evaluations are queryable by `request_id`.
- Validation failures do not create stored decision records.
- The service keeps decision records in local runtime memory. Records may disappear after service restart.
- Exact validation error body fields are framework-defined.
