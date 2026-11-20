# TREXO Release Notes

## v1.0.0-rc1 — Unified Release Candidate

**Date:** 2026-11-20
**Branch:** `integration/unified-release-candidate`
**Base:** `8daef80` (main)
**Status:** Release candidate — local only, not pushed, not deployed, **not production-ready**

---

## Highlights

This is the first build that combines the audited TREXO ML core, the Claude retail-intelligence package and the React store application behind one tested API.

- **Unified FastAPI backend** with 44 operations covering store operations, ML inference, retail intelligence and model management.
- **React frontend connected to the backend** through a new REST adapter, with the original mock services preserved as an offline fallback.
- **New ML Intelligence console** at `/intelligence`: model registry, portfolio dead-stock risk, demand forecasts and published retail insights.
- **Retail package merged additively**: inventory ledger, ageing/priority, pricing scenarios, bundles, customer intelligence, recovery, MILP optimiser, feedback and replay.
- **Server-side authentication**: HMAC bearer tokens; admin-gated, checksum-verified model activation.
- **Reproducible ML**: re-training produced byte-identical artifacts; an independent evaluation reproduced the registered metrics exactly.

---

## Commits

| Commit | Description |
|---|---|
| `8daef80` | Initial TREXO-INDIA commit (base, unchanged) |
| `3cc1669` | Merge retail intelligence package + add unified FastAPI backend (37 tests) |
| `1201b77` | Connect frontend to backend, add ML console |
| *(this commit)* | Independent evaluation script + nine release documents |

`main` was never modified.

---

## Added

### Backend

- `backend/trexo_api/` — app factory, config, security, schemas, SQLite store, business logic, ML facade, routers.
- `backend/tests/` — 37 API tests.
- `backend/requirements.txt` — FastAPI 0.165.0, Uvicorn 0.41.0, httpx 0.28.1, plus the ML lockfile.
- Seed data extracted from the frontend demo state (`backend/trexo_api/store/seed_data.json`).
- Synthetic 180-day ML sales history, isolated in its own table and labelled.

### Frontend

- `src/services/apiClient.ts`, `apiServices.ts`, `mlService.ts`.
- `src/pages/MlIntelligencePage.tsx` + `/intelligence` route and sidebar entry.
- `.env.example` for `VITE_USE_MOCK` / `VITE_API_BASE_URL`.
- Mock services remain the default; set `VITE_USE_MOCK=false` to use the backend.

### ML

- Retail package, tests, scripts, models, reports and docs merged without overwriting anything.
- `scripts/ml_independent_evaluation.py` — leakage-free re-evaluation of the deployed rule.
- New training versions created; previous versions retained.

### Documentation

- `TREXO_SYSTEM_INTEGRATION_REPORT.md`
- `TREXO_ML_COMPARISON_REPORT.md`
- `TREXO_FINAL_MODEL_TRAINING_REPORT.md`
- `TREXO_MODEL_EVALUATION_REPORT.md`
- `TREXO_ARCHITECTURE.md`
- `TREXO_API_DOCUMENTATION.md`
- `TREXO_DEPLOYMENT_GUIDE.md`
- `TREXO_TESTING_REPORT.md`
- `TREXO_RELEASE_NOTES.md` (this file)

---

## Changed

- Frontend dependency fix: esbuild `^0.25.0` → `^0.28.0` for Vite 8 compatibility.
- `frontend/src/services/index.ts` now selects mock or API instead of always returning the mock.
- Owner authentication in API mode happens server-side; the browser stores only a short-lived token.
- `.gitignore` extended for backend data, databases, auth secrets and frontend build outputs.

---

## Preserved

- All existing model versions, including rejected challengers.
- All existing datasets, reports, governance records and docs.
- D01 handling: invoices `A563185`–`A563187` excluded from product analytics, original records untouched.
- Both source ZIPs, verified by SHA-256.

---

## Verification

| Check | Result |
|---|---|
| Python tests | 141 passed, 4 skipped |
| Backend tests | 37 passed |
| Frontend tests | 27 passed (6 files) |
| Type-check | pass |
| Production build | pass |
| Independent ML evaluation | matches registered metrics |
| ZIP hashes | unchanged |
| Secret scan | no committed keys |

---

## Upgrade / run

```powershell
python -m pip install -r backend\requirements.txt

# API
.venv\Scripts\python.exe -m uvicorn trexo_api.main:app --app-dir backend --host 127.0.0.1 --port 8000

# UI (separate terminal)
cd frontend
npm install
# .env.local: VITE_USE_MOCK=false
npm run dev
```

See `TREXO_DEPLOYMENT_GUIDE.md` for environment variables, model rollback and troubleshooting.

---

## Known issues and limitations

1. **Not production-ready.** Demo data only; no real ledger, stock or cost data.
2. **Mock passcode is not security.** `123456789` remains for offline demos only.
3. **No HTTPS, rate limiting or user management.**
4. **SQLite single-node only.** Model activation relies on a local `LATEST` file.
5. **Bundle size warning** (~1.1 MB JS, 316 kB gzip); code-splitting pending.
6. **API adapter has no dedicated unit tests** (covered by type-check, build and manual end-to-end checks).
7. **Retail profit benefit is not demonstrated.** Elasticity is observational; price-aware forecasting gains ~2%.
8. **Dead-stock target is demand inactivity**, not physical dead stock; trapped capital cannot be computed without inventory data.
9. **Demo ML history is synthetic** and must not be read as model performance evidence.

---

## Next steps

1. Review this release candidate and the nine reports.
2. Connect a real shop ledger and verified stock/cost data.
3. Decide on HTTPS, rate limiting and identity management.
4. Run a pilot; compare recommendations with outcomes before enabling them.
5. Add E2E browser tests and adapter unit tests.
6. Only then approve a push and deployment.
