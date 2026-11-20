# TREXO Architecture

**Release candidate:** `integration/unified-release-candidate`
**Date:** 2026-11-20

---

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────┐
│ Browser (React 19 + Vite 8 + TypeScript + Tailwind 4)                │
│                                                                      │
│  Pages: Dashboard / Counter / Inventory / Rescue / Restock /         │
│         Customers / Reports / ML Intelligence                        │
│                                                                      │
│  Zustand store ──▶ services (TrexoServices contract)                 │
│                      ├── mockServices      (VITE_USE_MOCK=true)      │
│                      └── apiServices       (VITE_USE_MOCK=false)     │
│                              │                                       │
│  authService ────────────────┤ bearer token in sessionStorage        │
│  mlService ──────────────────┘                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │ HTTPS/HTTP JSON (camelCase)
┌──────────────────────────────▼───────────────────────────────────────┐
│ FastAPI backend (backend/trexo_api)                                  │
│                                                                      │
│  routers: health | auth | store | ml | retail | models               │
│  security: HMAC bearer token, passcode check, admin token            │
│  services/ml: lazy InferenceService + RetailIntelligenceService      │
│  store/service: business rules + SQLite persistence                  │
│  schemas: pydantic camelCase contracts, strict validation            │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
      ┌─────────▼─────────┐          ┌──────────▼─────────────┐
      │ SQLite            │          │ src/trexo/ml           │
      │ backend/data/     │          │  inference service     │
      │  trexo.db         │          │  retail service        │
      │  (git-ignored)    │          │  registry + artifacts  │
      └───────────────────┘          └──────────┬─────────────┘
                                                │ checksum-verified
                                     ┌──────────▼─────────────┐
                                     │ models/<kind>/<ver>/   │
                                     │ reports/, data/        │
                                     └────────────────────────┘
```

---

## 2. Frontend

| Layer | Files | Notes |
|---|---|---|
| Routing | `src/App.tsx` | Login gate; authenticated routes incl. `/intelligence` |
| Shell | `src/components/AppShell.tsx` | Sidebar nav, header, toasts, UPI/shortcuts modals |
| State | `src/store/useLedgerStore.ts` | Zustand store; loads all domain data via `services` |
| Contracts | `src/services/interfaces.ts` | `TrexoServices`: products, billing, inventory, suppliers, customers, forecast, reports |
| Mock | `src/services/mockServices.ts` | Original in-browser implementation, unchanged as fallback |
| API | `src/services/apiServices.ts` | REST adapter; whitelists patch fields for the strict backend |
| HTTP | `src/services/apiClient.ts` | fetch, token handling, `ApiClientError` with stable codes |
| Auth | `src/services/authService.ts` | Mock gate or server login depending on `VITE_USE_MOCK` |
| ML | `src/services/mlService.ts`, `src/pages/MlIntelligencePage.tsx` | Read-only model registry, portfolio, retail insights |
| Types | `src/types/domain.ts` | Shared domain model |

Configuration:

- `VITE_USE_MOCK` (default `true`): mock services vs API.
- `VITE_API_BASE_URL` (default `http://127.0.0.1:8000/api/v1`).

The UI never computes authoritative business rules in API mode: sale totals, stock clamping, duplicate-UPI checks, invoice numbering and repayment limits are server-side.

---

## 3. Backend

### 3.1 Request lifecycle

1. `main.py` creates the app, sets up lifespan (SQLite + `StoreService` with seed), CORS, timing/security headers.
2. `require_auth` validates the HMAC bearer token on every `/store`, `/ml`, `/retail`, `/models` route.
3. Pydantic validates the body against a strict camelCase schema (`extra="forbid"`).
4. The router delegates to a service:
   - store operations → `StoreService` (SQLite);
   - ML operations → `services/ml.py` facade → `InferenceService` / `RetailIntelligenceService`.
5. Exceptions are translated to one JSON envelope.

### 3.2 Error envelope

```json
{ "error": { "code": "DUPLICATE_UPI_REF", "message": "...", "details": null } }
```

- `ApiError` — application errors with stable codes and status.
- `StoreError` — business-rule violations (400/404/409).
- `RequestValidationError` — `VALIDATION_ERROR` (422) with encoded details.
- Unhandled — `INTERNAL_ERROR` (500); the traceback is logged, never returned.

### 3.3 Authentication and authorization

| Mechanism | Detail |
|---|---|
| Login | `POST /api/v1/auth/login` with the owner passcode; returns an HMAC-signed bearer token |
| Secret | `TREXO_AUTH_SECRET` env var, else generated once into `backend/data/.auth_secret` (git-ignored, chmod 600 where possible) |
| Passcode | `TREXO_OWNER_PASSCODE_HASH` (PBKDF2-SHA256, preferred); no default credential |
| TTL | `TREXO_TOKEN_TTL_SECONDS`, default 12 h |
| Admin | Model activation requires `X-Admin-Token` equal to `TREXO_ADMIN_TOKEN`; if unset the endpoint returns 503 `ADMIN_DISABLED` |
| CORS | `TREXO_CORS_ORIGINS`, comma-separated, no credentials |

Tokens are not stored server-side; expiry is embedded and signature-checked with constant-time comparison.

### 3.4 Storage schema (SQLite)

| Table | Purpose |
|---|---|
| `products` | Catalogue, stock, pricing, reorder flags, supplier link |
| `sales` | Completed invoices with line items (JSON) |
| `customers` | Udhaar balances |
| `customer_payments` | Confirmed payments and failed/cancelled attempts |
| `suppliers` | Distributors and lead times |
| `supplier_returns` | Return-to-supplier records and slip timestamps |
| `purchase_orders` | POs generated from forecasts |
| `ml_sales_history` | **Synthetic** daily sales rows for ML demos (separate from sales) |
| `meta` | Invoice/PO sequences, confirmed UPI/payment references |

Seed data is the exact frontend demo state (`backend/trexo_api/store/seed_data.json`), re-based to the current date on first run. `ml_sales_history` is deterministic (seed 20261120) and explicitly synthetic.

### 3.5 ML service loading

- `services/ml.py` imports `trexo.ml` lazily and caches one `InferenceService` and one `RetailIntelligenceService` per process behind an `RLock`.
- Missing artifacts raise `MODEL_UNAVAILABLE` (503); no prediction is fabricated.
- ML exceptions map to `INVALID_REQUEST` (422), `MODEL_UNAVAILABLE` (503) or `ML_ERROR` (500).
- The registry lists versions by scanning `models/<kind>/`, reads `LATEST`, and validates `metadata.json`.
- Activation verifies version-name safety, artifact existence, and checksum round-trip before rewriting `LATEST`.

---

## 4. Data flow examples

### Complete a sale

```
Counter UI → apiServices.billing.completeSale
  → POST /store/sales
    → validate schema
    → StoreService: clamp qty, compute totals, dead-stock rescue flag,
      decrement stock, update avg daily sales, duplicate-UPI check,
      udhaar guard, invoice sequence
    → persist sale + product updates + history row
  → 201 Sale (camelCase)
→ Zustand refresh / optimistic UI
```

Validation failures occur **before** any mutation, so a rejected udhaar or duplicate-UPI sale does not change stock.

### ML portfolio scan

```
ML page → mlService.portfolio(4)
  → POST /ml/portfolio
    → StoreService.ml_product_catalog()  (products + synthetic history)
    → for each product: InferenceService.dead_stock_detection + demand_forecast
    → per-product OK / ERROR, explicit synthetic-data note
  → render risk score, status, 4-week forecast, method
```

---

## 5. Governance and safety boundaries

- **D01:** bad-debt invoices are excluded at the ML boundary with a warning; source rows are never deleted.
- **No fabrication:** insufficient history returns `NO_VALID_SALES`; missing artifacts return 503.
- **Human approval:** every recommendation carries a disclaimer; no action is auto-executed.
- **Version immutability:** training creates new directories; no version is overwritten.
- **Secrets:** none committed. The only embedded credential is the documented mock-mode demo passcode.

---

## 6. Deployment topology (intended)

Single process for the release candidate:

- Uvicorn serves the API on `127.0.0.1:8000` (or behind a reverse proxy).
- Vite dev server on `5173` for development, or a static build served by the backend (`frontend/dist` mount) / any static host.
- SQLite file and `models/` on local disk. For multi-instance deployment, move storage to a shared database and object store, and coordinate `LATEST` through a registry service.

---

## 7. Extension points

| Need | Where to change |
|---|---|
| New store field | `schemas/domain.py`, `store/service.py`, `store/seed_data.json`, frontend `types/domain.ts` |
| New ML endpoint | `routers/ml.py`, `services/ml.py`, request schema in `schemas/api.py` |
| New model kind | train script → `models/<kind>/`, add to `services/ml.py` |
| Different auth | replace `security.py` guards; routers already depend on them |
| Real database | replace `store/db.py` implementation; keep the `StoreService` API |
