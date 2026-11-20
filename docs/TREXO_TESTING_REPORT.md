# TREXO Testing Report

**Date:** 2026-11-20
**Branch:** `integration/unified-release-candidate`
**Environment:** Windows, Python 3.11.9, `.venv`, Node 20+

Every result below is from a command run during this integration, not from an earlier report.

---

## 1. Summary

| Suite | Command | Result |
|---|---|---|
| Python (all) | `python -m pytest -q` | **141 passed, 4 skipped** in 38.32 s |
| Backend API | `python -m pytest backend/tests -q` | **37 passed** in 5.19 s |
| Retail package (as delivered) | retail test suite | **98 passed, 4 skipped, 4 subtests** in 7.10 s |
| Frontend unit | `npm test -- --run` | **27 passed**, 6 files |
| Type-check | `npm run lint` (`tsc --noEmit`) | **pass**, no diagnostics |
| Production build | `npm run build` | **pass** in 1.50 s (bundle-size warning only) |
| Independent ML evaluation | `scripts/ml_independent_evaluation.py` | reproduced registered metrics exactly |

Skipped tests are environment/data gates in the existing ML suite (they were skipped before the integration too), not failures.

---

## 2. Python suite composition

| Area | Approx. tests | Notes |
|---|---:|---|
| Core ML (features, labels, classifier, calibration, forecasting, movement, reorder, anomaly, recommendations, registry, inference) | 74 | pre-existing |
| Retail (`tests/ml/retail/`) | 30 | added by the merge |
| Backend API (`backend/tests/`) | 37 | new |
| **Total** | **141** | plus 4 skipped |

### Backend test files

| File | Coverage |
|---|---|
| `backend/tests/test_health_auth.py` | health/root/livez, auth required, bad token, wrong password, validation, model listing, model-kind 404, admin endpoint disabled |
| `backend/tests/test_store_api.py` | product shapes, forecast contract and horizon validation, sales summary totals, sale flow, stock decrement, duplicate UPI, stock clamping, validation errors, udhaar guards (+ atomicity), stock adjustment, product create/update/discount/stop-reorder, supplier returns and slips, customer payments/attempts, purchase orders, ML catalog |
| `backend/tests/test_ml_api.py` | dead-stock prediction contract, `NO_VALID_SALES`, non-product code rejection, D01 warning, forecast horizon validation, reorder insufficient inputs, anomaly/movement, invalid date, portfolio scan + filter, management summary, retail pricing validation, bundles/insights, inventory ledger |

### Test database isolation

Backend tests use a per-session temporary SQLite file (`tmp_path_factory`) so they never touch `backend/data/trexo.db`.

---

## 3. Frontend tests

| File | Focus |
|---|---|
| `authService.test.ts` | session/auth gate behaviour |
| `mockServices.test.ts` | business logic retained in mock mode |
| `money.test.ts` | paise/rupee formatting and stock predicates |
| `reports.test.ts` | CSV/report aggregation |
| `shortcuts.test.ts` | keyboard shortcut parsing |
| `upi.test.ts` | UPI ID validation |

Result: `Test Files 6 passed (6)`, `Tests 27 passed (27)`.

The new API adapter, client and ML service are covered by `tsc --noEmit` and the production build rather than dedicated unit tests; they are exercised end-to-end manually against the backend (see §6). Adding adapter-level tests is recommended.

---

## 4. Type-check and build

```
> tsc --noEmit
(no output — success)

> vite build
dist/assets/index-*.js   1,113.12 kB │ gzip: 315.64 kB
✓ built in 1.50s
```

Warnings (non-blocking):

- Vite config uses `__dirname` with a future-native loader (cosmetic).
- Chunk > 500 kB; code-splitting recommended.

---

## 5. Manual API verification

A scripted `TestClient` session exercised the full stack after seeding:

| Check | Result |
|---|---|
| `GET /health` | 200, `database: ok`, models loaded (`status: OK`) |
| `POST /auth/login` (correct) | 200 with token |
| `POST /auth/login` (wrong) | 401 |
| Unauthenticated store call | 401 |
| Products / sales / customers / suppliers / forecast / summary | 200 with expected shapes |
| `GET /models` | 200, 8 kinds |
| `POST /ml/dead-stock` | 200, `prediction: "Normal Moving Stock"`, deployed predictor `baseline_recency_rule` |
| `POST /ml/forecast` (4 weeks) | 200, SES method, 4 weekly values |
| `POST /ml/reorder`, `/anomalies`, `/movement` | 200 |
| `POST /ml/portfolio` (all products) | 200, 16 evaluated, 0 failures |
| `POST /retail/pricing/scenarios` | 200 |

One bug was found and fixed here: the catalogue's `as_of` was a timestamp while ML dates were date-only, causing a tz-naive/tz-aware comparison error. It now emits a date string.

---

## 6. Contract-level checks

- **Camel-case contract:** backend pydantic aliases match `frontend/src/types/domain.ts`; verified by fetching every store collection and diffing keys against the TypeScript interfaces.
- **Strict schemas:** `extra="forbid"` on store and ML bodies; unknown fields return 422. The frontend adapter deliberately whitelists PATCH fields.
- **Atomicity:** a failed udhaar sale with a missing customer leaves stock unchanged (explicit test).
- **Duplicate references:** repeated UPI transaction references return 409 for both sales and repayments.
- **D01:** a sale line with an excluded invoice produces a governance warning; the record is retained in the caller's data.

---

## 7. Model evaluation tests

The independent script:

1. rebuilds the chronological splits with public functions;
2. fits recency calibration on training cutoffs only;
3. selects the threshold on validation (inline F2);
4. computes test metrics with scikit-learn directly.

It reproduced the deployed rule's registered values exactly:

| Metric | Registered | Independent |
|---|---:|---:|
| Validation PR-AUC | 0.7611267 | 0.7611267 |
| Test PR-AUC | 0.8019788 | 0.8019788 |
| Test ROC-AUC | 0.9469213 | 0.9469213 |

Training re-runs also produced byte-identical artifact checksums (see `TREXO_FINAL_MODEL_TRAINING_REPORT.md`).

---

## 8. Security checks

| Check | Result |
|---|---|
| `git grep` for API keys / client secrets in source | no findings |
| `.env` files tracked | none (`frontend/.env.example` only) |
| `node_modules`, `dist`, `*.db`, `.auth_secret`, model artifacts tracked | none (ignored) |
| Passcode in browser (API mode) | never stored; exchanged for a signed token |
| Admin endpoint without token | 503 `ADMIN_DISABLED` (tested) |
| Error responses leak tracebacks | no; generic 500 envelope |
| ZIP integrity | both hashes unchanged |

Known exception: mock mode retains the documented demo passcode `123456789` because it is a client-only offline demo; it is clearly labelled and unused in API mode.

---

## 9. Not covered

- Real POS integration, concurrency/load testing, multi-instance behavior.
- Browser E2E automation (Playwright/Cypress) — manual smoke only.
- HTTPS/TLS, reverse proxy, rate limiting.
- Real shop inventory/cost data (none exists).
- The API adapter lacks dedicated unit tests.
- Retail model behaviour on real shop data.

---

## 10. Reproduce

```powershell
# From the repository root
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe scripts\ml_independent_evaluation.py

cd frontend
npm run lint
npm test -- --run
npm run build
```

Raw full-suite output was saved to the git-ignored file `reports/ml/unified_pytest_results.txt` during this run.
