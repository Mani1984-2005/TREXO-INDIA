# TREXO API Documentation

**Base URL:** `http://127.0.0.1:8000/api/v1`
**Interactive docs:** `GET /docs` (Swagger UI), `GET /openapi.json`
**Version:** `1.0.0`
**Date:** 2026-11-20

---

## 1. Conventions

- All bodies are JSON. Store-domain payloads use **camelCase**; ML payloads use **snake_case** (matching the ML package).
- Money is always **integer paise** in the store domain; ML prices are decimal currency units.
- Timestamps are ISO-8601.
- Errors use one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": []
  }
}
```

| Status | Meaning |
|---|---|
| 200 / 201 | Success |
| 204 | Deleted, no body |
| 400 | Business rule violation (`StoreError`) |
| 401 | Missing/invalid/expired token, or wrong passcode |
| 403 | Admin token required/invalid |
| 404 | Resource not found |
| 409 | Conflict (duplicate reference, invalid model version) |
| 422 | Schema/validation error |
| 500 | Unhandled server error (`INTERNAL_ERROR`) |
| 503 | Model artifacts unavailable or admin management disabled |

### Authentication

```http
POST /api/v1/auth/login
Content-Type: application/json

{ "password": "<owner passcode>" }
```

```json
{ "token": "<payload>.<signature>", "expiresIn": 43200, "tokenType": "bearer" }
```

Send `Authorization: Bearer <token>` on every other endpoint below.
Model activation additionally requires `X-Admin-Token`.

Unauthenticated probes: `GET /`, `GET /livez`, `GET /api/v1/health`, `POST /api/v1/auth/login`.

---

## 2. Health

### `GET /health` (public)

```json
{
  "status": "ok | degraded",
  "service": "trexo-india-api",
  "version": "1.0.0",
  "database": "ok | error: ...",
  "models": { "status": "OK", "schema_version": "1.0", "dead_stock": {}, "forecasting": {}, "movement": {} }
}
```

`degraded` means the database is unreachable or model artifacts cannot be loaded. The endpoint never raises.

### `GET /livez` (public)

Plain text `ok` — liveness only.

---

## 3. Store — products

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/store/products` | — | `Product[]` |
| POST | `/store/products` | `ProductCreateInput` | `Product` (201) |
| PATCH | `/store/products/{id}` | partial product fields | `Product` |
| POST | `/store/products/{id}/counter-discount` | `{ "pricePaise": 9000 \| null }` | `Product` |
| POST | `/store/products/{id}/stop-reordering` | `{ "stop": true }` | `Product` |
| POST | `/store/products/{id}/stock` | `{ "deltaQty": 5 }` | `Product` |

`ProductCreateInput`:

```json
{
  "name": "Test Rice 1kg",
  "sku": "TST-1",
  "category": "Grains & Atta",
  "unit": "1 kg",
  "mrpPaise": 10000,
  "costPaise": 8000,
  "sellingPricePaise": 9500,
  "stockQty": 10,
  "reorderLevel": 3,
  "expiryDate": null,
  "supplierId": "sup-4"
}
```

Notes:

- `PATCH` accepts only mutable fields (`name`, `sku`, `category`, `unit`, prices, `stockQty`, `reorderLevel`, `expiryDate`, `supplierId`, `stopReordering`). Unknown fields are rejected.
- Counter discount is cleared automatically when it is not strictly below the selling price, or when stock reaches zero after a sale.
- `deltaQty` must be non-zero; stock never goes below zero.
- Unknown product → 404 `PRODUCT_NOT_FOUND`.

`Product`:

```json
{
  "id": "prod-1", "sku": "GRN-001", "name": "Aashirvaad Atta 5kg",
  "category": "Grains & Atta", "unit": "5 kg",
  "mrpPaise": 27500, "costPaise": 21800, "sellingPricePaise": 26000,
  "counterDiscountPricePaise": null, "stockQty": 18, "reorderLevel": 6,
  "avgDailySales": 2.4, "lastSoldAt": "...", "expiryDate": null,
  "supplierId": "sup-4", "stopReordering": false
}
```

---

## 4. Store — billing

### `GET /store/sales` → `Sale[]`

### `POST /store/sales` → `Sale` (201)

```json
{
  "items": [{ "productId": "prod-1", "qty": 2 }],
  "paymentMethod": "cash | upi | udhaar",
  "customerId": null,
  "upiTransactionRef": "UPI-...",
  "upiUtrNumber": "123456789012",
  "upiIdUsed": "store@bank",
  "paymentStatus": "confirmed",
  "isDemoPayment": true
}
```

Server-side rules:

- quantities are floored to at least 1 and clamped to available stock;
- a stock-out product fails with 400 `OUT_OF_STOCK`;
- `udhaar` requires an existing customer (400 `CUSTOMER_REQUIRED` / 404 `CUSTOMER_NOT_FOUND`);
- duplicate `upiTransactionRef` → 409 `DUPLICATE_UPI_REF`;
- invoice numbers are sequential (`TRX-<n>`);
- dead-stock / near-expiry lines set `rescuedDeadStockPaise`;
- **all validation happens before any mutation**, so rejected sales do not change stock or balances.

---

## 5. Store — customers and payments

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/store/customers` | — | `Customer[]` |
| POST | `/store/customers` | `{ name, phone, address, openingDuePaise? }` | `Customer` (201) |
| GET | `/store/customer-payments` | — | `CustomerPaymentEntry[]` |
| POST | `/store/customers/{id}/payments` | `{ amountPaise, meta? }` | `{ customer, payment }` |
| POST | `/store/customers/{id}/payment-attempts` | `{ amountPaise, meta }` | `CustomerPaymentEntry` |

`meta`: `{ paymentMethod: "cash"|"upi", transactionRef?, utrNumber?, upiIdUsed?, status?, isDemo? }`.

Rules: amount > 0; cannot exceed outstanding due (`AMOUNT_EXCEEDS_DUE`); duplicate reference rejected (409); failed/cancelled attempts are recorded **without** changing the balance.

---

## 6. Store — suppliers and returns

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/store/suppliers` | — | `Supplier[]` |
| GET | `/store/supplier-returns` | — | `SupplierReturnItem[]` |
| POST | `/store/supplier-returns` | `{ productId, qty, reason }` | `{ product, returnItem }` (201) |
| POST | `/store/supplier-returns/mark-slips` | `{ returnIds: [] }` | `SupplierReturnItem[]` |
| DELETE | `/store/supplier-returns/{id}` | — | 204 |

`reason` ∈ `Dead stock (slow moving)`, `Near expiry`, `Damaged packaging`, `Excess supply`.
Return quantity is clamped to available stock. Deleting a return record does not restore stock.

---

## 7. Store — forecasting and purchasing

### `GET /store/forecast?horizon=1W|1M|6M|1Y` → `ForecastRow[]`

Deterministic planning forecast from stored `avgDailySales`, stock and supplier lead time. Not the ML forecast. Rows are sorted by urgency.

### `GET /store/purchase-orders` → `PurchaseOrder[]`

### `POST /store/purchase-orders` → `PurchaseOrder` (201)

Body is an array of PO items without `lineTotalPaise`:

```json
[
  { "productId": "prod-1", "sku": "GRN-001", "name": "Atta",
    "supplierId": "sup-4", "supplierName": "National Grain & Oil Depot",
    "qty": 2, "unitCostPaise": 21800 }
]
```

Empty (after removing zero-quantity lines) → 400 `EMPTY_PO`. PO numbers are `PO-<year>-<seq>`.

---

## 8. Store — reports

### `GET /store/reports/sales-summary` → `SalesSummary`

Totals by payment method, today's revenue/bill count, 7-day series and top-6 products, all in paise/rupees where indicated.

### `POST /store/reports/reset-demo` → `{ "status": "OK", "message": "Demo data reset" }`

Resets the domain tables to seed and re-seeds history. Intended for demos only.

### `GET /store/ml/catalog`

Products shaped for the ML layer: `product_id` (SKU), `sales_history`, `as_of`, `on_hand_qty`, `unit_cost`, `lead_time_days`. The history is **synthetic** demo data.

---

## 9. Machine learning (`/ml`)

All ML endpoints require a bearer token. Request bodies follow `MLRequest`:

```json
{
  "product_id": "GRN-001",
  "sales_history": [{ "date": "2011-01-01", "quantity": 2, "unit_price": 3.5, "invoice_no": "INV1" }],
  "as_of": "2011-06-01",
  "description": "Atta",
  "on_hand_qty": 12,
  "unit_cost": 3.5,
  "lead_time_days": 3,
  "service_level": 0.95
}
```

Limits: `sales_history` ≤ 20,000 records. Records with invoice numbers `A563185`–`A563187` are excluded by D01 and reported in `warnings`.

| Method | Path | Notes |
|---|---|---|
| POST | `/ml/dead-stock` | risk score, classification, warnings; `NO_VALID_SALES` if no usable history |
| POST | `/ml/dead-stock/risk` | same as `/ml/dead-stock` |
| POST | `/ml/forecast` | plus `horizon_weeks` (1–8); weekly and total units |
| POST | `/ml/movement` | ABC-XYZ and speed class |
| POST | `/ml/anomalies` | transaction-quality flags |
| POST | `/ml/reorder` | `INSUFFICIENT_INPUTS` when inventory inputs are missing |
| POST | `/ml/reduction-actions` | evidence-based reduction suggestions |
| GET | `/ml/summary` | management summary |
| POST | `/ml/portfolio` | runs dead-stock + forecast over the catalogue |

`POST /ml/portfolio` body:

```json
{ "horizon_weeks": 4, "product_ids": ["GRN-001"], "as_of": null }
```

Response: `status`, `evaluated`, `failures`, `syntheticHistoryNote`, and per-product `results` with `deadStock` / `forecast` or an `error` object. One failing product does not abort the scan; a missing model does (503).

Example dead-stock response fields: `status`, `prediction`, `dead_stock_risk_score`, `classification`, `model_version`, `predictor` (`baseline_recency_rule`), `status_type`, `human_review_required`, `warnings`, `as_of`.

---

## 10. Retail intelligence (`/retail`)

| Method | Path | Body |
|---|---|---|
| POST | `/retail/inventory/balances` | `{ events: [...] }` (1–20,000) |
| POST | `/retail/stock-priority` | ledger events + `velocity_window_days` |
| POST | `/retail/pricing/scenarios` | `{ price, stock, daily_demand, cost?, horizon_days?, elasticity?, conservative? }` |
| POST | `/retail/bundles/recommendations` | `{ product_id, min_lift?, min_conf?, top_k? }` |
| POST | `/retail/recovery/plan` | ledger events + `prices`, `costs`, rules |
| GET | `/retail/insights` | read-only published experiment JSON/CSV |

Ledger event:

```json
{ "event_id": "e1", "product_id": "P1", "location": "MAIN",
  "ts": "2011-01-01", "type": "OPENING", "qty": 10, "unit_cost": 5 }
```

Pricing rejects `elasticity >= 0` (422). Bundle recommendations return `candidates: []` for an unknown product rather than inventing pairs. Every recommendation response includes an approval-required disclaimer.

---

## 11. Model management (`/models`)

| Method | Path | Auth | Result |
|---|---|---|---|
| GET | `/models` | bearer | `ModelInfo[]` |
| GET | `/models/{kind}` | bearer | `ModelInfo` |
| POST | `/models/{kind}/activate` | bearer + `X-Admin-Token` | `ModelInfo` |

```json
{ "kind": "dead_stock", "latest": "dead_stock-ml-1.1.0-...", "versions": ["..."], "metadata": {} }
```

Activation body: `{ "version": "dead_stock-ml-1.1.0-20261119T091454Z" }`.

Safety: version names cannot contain path separators or `..`; the target must exist; artifacts are checksum-verified by reloading the bundle before `LATEST` is rewritten. If `TREXO_ADMIN_TOKEN` is unset the endpoint is disabled (503 `ADMIN_DISABLED`).

---

## 12. Endpoint count

**44 operations** across health, auth, store, ML, retail and model management. The OpenAPI schema at `/openapi.json` is authoritative if this document and the code ever disagree.
