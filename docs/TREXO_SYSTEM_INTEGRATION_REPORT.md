# TREXO System Integration Report

**Date:** 2026-11-20
**Branch:** `integration/unified-release-candidate`
**Canonical repository:** `E:\TREXO-INDIA\TREXO-INDIA-ML\TREXO-INDIA`
**Base commit:** `8daef80` — *Initial commit: TREXO-INDIA*
**Release-candidate commits:** `3cc1669` (retail merge + backend), `1201b77` (frontend integration), plus the documentation/evaluation commit that contains this file.

---

## 1. Objective

Unify three previously separate pieces of work into one tested, documented repository:

1. The existing **TREXO-INDIA ML** repository (audited `ml-1.1.0` core, D01 governance, dead-stock, forecasting, movement, reorder, anomaly, recommendations, inference, registry).
2. The **Claude "RETAIL"** implementation delivered as `TREXO-INDIA-RETAIL.zip` (retail intelligence package, its own tests, scripts, models, reports and docs).
3. The **Google AI Studio React frontend** delivered as `smart-digital-munim.zip` (store-operations UI backed by an in-browser mock `TrexoServices` implementation).

The result must preserve every existing dataset, model version, report and governance record, and must not present unvalidated models as production-ready.

---

## 2. Inputs and integrity

| Input | Size (bytes) | SHA-256 | State |
|---|---:|---|---|
| `TREXO-INDIA-RETAIL.zip` | 42,388,627 | `7650556AB6C182D10EA64802D3BC132387B12A95D1571A4C7E03F487FE26178D` | untouched |
| `smart-digital-munim.zip` | 1,931,642 | `7C7F4E5D1E9464C957FDA730C2C1605474ED3FD72BB9A4D67080A4DFD576C815` | untouched |

Hashes were recorded before extraction and re-verified after the integration work; both match. The archives were only read, never modified or deleted.

A full pre-integration backup was created at
`E:\TREXO-INDIA\_backups\pre_integration_20261120T174257Z`
(`repo_all_refs.bundle` plus a 288-file worktree copy, 86.7 MB), and its path was written to `_backups\LATEST_BACKUP.txt`.

### Canonical-repository decision

`E:\TREXO-INDIA` (the outer folder) is an older pre-ML copy and is **not** a git repository. The real history, remote (`origin` = `https://github.com/Mani1984-2005/TREXO-INDIA.git`), models, reports and governance records live in `E:\TREXO-INDIA\TREXO-INDIA-ML\TREXO-INDIA`. All integration work was therefore done there, on a dedicated branch. `main` was not modified, and nothing was pushed.

---

## 3. Integration decisions

| ID | Decision | Rationale |
|---|---|---|
| I1 | Keep the existing `ml-1.1.0` core as the base | It has the D01 governance decision, richer classifier/anomaly/recommendation/inference layer and the audited registry. |
| I2 | Merge only the **additive** `trexo.ml.retail` package, its tests, scripts, docs, model artifacts and reports | The Claude fork was based on an older `1.0.0` core; replacing the base would have discarded the newer audited work. |
| I3 | Never overwrite a model version | Existing bundles were left in place; new training runs create timestamped versions. |
| I4 | Backend as a thin, validated FastAPI layer over `src/trexo/ml` | Avoids duplicating model logic and keeps one source of truth for inference. |
| I5 | SQLite store domain mirroring the frontend `TrexoServices` contract | Lets the React app switch from mock to API without UI rewrites. |
| I6 | Keep mock services as the default/fallback | Offline demos and the existing test suite keep working; `VITE_USE_MOCK=false` selects the API. |
| I7 | HMAC bearer token + server-side passcode | Removes credential checks from the browser in API mode. Admin/rollback endpoints require a separate `TREXO_ADMIN_TOKEN`. |
| I8 | D01 (invoices `A563185`–`A563187`) remains an exclusion | Bad-debt invoices are financial events, not product demand. Original records stay intact; the ML layer excludes and **warns**, never deletes. |
| I9 | Synthetic demo sales history is labelled synthetic | The store seed has no real sales time-series; generated history is isolated in `ml_sales_history` and never mixed into real report tables. |

---

## 4. What was integrated

### 4.1 Retail package (additive)

`src/trexo/ml/retail/` — inventory ledger, ageing, selling priority, pricing/elasticity scenarios, bundle recommendations, customer/RFM intelligence, recovery engine, profit optimiser, feedback store, simulation replay, and `RetailIntelligenceService`.

Supporting additions, with no file overwritten:

- `tests/ml/retail/` — 30 retail tests.
- `scripts/retail_*.py` — six experiment/training/doc scripts.
- `docs/` — 14 retail documents.
- `models/pricing`, `models/bundles`, `models/customers`, `models/forecasting_price` — new kinds only.
- `reports/ml/retail/` — experiment outputs.

### 4.2 Unified backend (`backend/`)

| Module | Responsibility |
|---|---|
| `trexo_api/main.py` | App factory, CORS, error envelopes, security headers, optional static frontend mount |
| `trexo_api/config.py` | Paths, passcode, TTL, CORS origins, admin token, auth secret persistence |
| `trexo_api/security.py` | HMAC token issue/verify, passcode check, `require_auth`, `require_admin` |
| `trexo_api/schemas/domain.py` | camelCase pydantic contracts mirroring `frontend/src/types/domain.ts` |
| `trexo_api/schemas/api.py` | ML request schemas, health and model envelopes |
| `trexo_api/store/db.py` | SQLite persistence, history table, meta, reset |
| `trexo_api/store/service.py` | Store business rules ported from `mockServices.ts` |
| `trexo_api/store/seed_data.json` | Exact frontend seed state (16 products, suppliers, customers, sales, etc.) |
| `trexo_api/services/ml.py` | Lazy model loading, error translation, registry listing/activation |
| `trexo_api/routers/` | health, auth, store, ml, retail, models |
| `backend/tests/` | 37 API tests |

FastAPI `0.165.0`, Uvicorn `0.41.0`, httpx `0.28.1` were added to the project virtualenv; `backend/requirements.txt` pins them and re-includes `requirements-lock.txt`.

The backend exposes **44 operations** (see `TREXO_API_DOCUMENTATION.md`).

### 4.3 Frontend (`frontend/`)

- Copied into the repository, `package.json` esbuild range corrected (`^0.25.0` → `^0.28.0`) to satisfy Vite 8, `npm install` completed (278 packages).
- `src/services/apiClient.ts` — fetch wrapper, bearer token in `sessionStorage`, stable `ApiClientError` codes.
- `src/services/apiServices.ts` — REST implementation of the full `TrexoServices` contract.
- `src/services/index.ts` — selects mock vs API from `VITE_USE_MOCK`.
- `src/services/authService.ts` — server login in API mode; the old client-side gate remains only in mock mode.
- `src/services/mlService.ts` + `src/pages/MlIntelligencePage.tsx` — read-only ML console (model registry, portfolio risk/forecast, published retail insights), route `/intelligence`, sidebar entry.
- `.env.example` now documents `VITE_USE_MOCK` and `VITE_API_BASE_URL`; the unused Gemini placeholder was removed.

Existing design, routes, state store and components were preserved. The ML page follows the existing `DesignSystem` primitives.

---

## 5. Verification summary

| Check | Result |
|---|---|
| Full Python suite (`pytest -q`) | **141 passed, 4 skipped** (38.3 s) |
| Backend API suite | **37 passed** |
| Retail suite (as delivered) | **98 passed, 4 skipped, 4 subtests** |
| Frontend unit tests (`vitest run`) | **27 passed** across 6 files |
| Type-check (`tsc --noEmit`) | **pass** |
| Production build (`vite build`) | **pass** (1.50 s; bundle-size warning only) |
| Independent ML evaluation | matches registered out-of-time metrics exactly (see `TREXO_MODEL_EVALUATION_REPORT.md`) |
| Training reproducibility | re-run produced **byte-identical artifact checksums** and identical metrics |
| ZIP integrity | both hashes unchanged |
| Secret scan | no API keys or production credentials committed; one documented demo passcode in mock mode |

---

## 6. Known gaps and risks

1. **The store domain is demo data.** The frontend seed is a realistic demo, not a live shop ledger. The backend persists it in SQLite; nothing connects to a real POS.
2. **Synthetic ML history.** `ml_sales_history` is generated from configured average daily sales so the ML console has data. It is labelled synthetic everywhere it is surfaced.
3. **Mock-mode passcode is not security.** `123456789` exists only for offline demos. In API mode the browser never verifies or stores it.
4. **No HTTPS, rate limiting, or user management.** Tokens are compact HMAC bearer tokens, not a full identity system.
5. **Model benefit is not demonstrated on real inventory.** Retail clearance replay showed no proven benefit; pricing is associational, not causal.
6. **Model activation is file-based.** `models/<kind>/LATEST` is rewritten after checksum verification. There is no multi-node coordination.
7. **Bundle size warning.** The single JS bundle is ~1.1 MB (315 kB gzip); code-splitting is recommended but was left out to avoid unrelated UI refactoring.
8. **No remote push, no deployment.** This is a local release candidate awaiting review.

---

## 7. Repository layout after integration

```
TREXO-INDIA/
├── backend/                 # FastAPI service + tests + requirements
├── frontend/                # React 19 / Vite 8 application + tests
├── src/trexo/ml/            # audited ML core + retail package
├── scripts/                 # ML training, evaluation, retail experiments
├── models/                  # versioned artifacts (git-ignored, multi-version)
├── reports/                 # metrics and experiment outputs (git-ignored)
├── data/                    # raw/processed data (git-ignored)
├── docs/                    # existing + retail + this release documentation
└── tests/                   # unit/integration tests (incl. retail)
```

---

## 8. Release-candidate status

**Status: integration complete, tests green, documentation complete, awaiting human review.**

Not production-ready. Before any deployment: connect a real ledger, obtain real stock/cost data, review D01 and consent decisions, add HTTPS/rate limiting, and run a pilot with verified inventory.
