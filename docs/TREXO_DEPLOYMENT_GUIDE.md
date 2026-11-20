# TREXO Deployment Guide

**Release candidate:** `integration/unified-release-candidate`
**Date:** 2026-11-20
**Scope:** Local / single-node deployment of the unified backend + frontend.

> This guide covers a release candidate, not a production rollout. See §8 before exposing it to real users.

---

## 1. Prerequisites

| Requirement | Version used |
|---|---|
| Python | 3.11.9 |
| Node.js | 20+ (npm bundled) |
| Git | any recent |
| OS | Windows (developed), Linux/macOS supported |
| Disk | ~1 GB for data/models/venv/node_modules |

Python dependencies are split:

- `requirements-lock.txt` — ML/data stack (already used by the repo).
- `backend/requirements.txt` — FastAPI/Uvicorn/httpx + `-r ../requirements-lock.txt`.

---

## 2. Backend setup

From the repository root:

```powershell
python -m venv ..\.venv              # or reuse an existing venv
..\.venv\Scripts\python.exe -m pip install --upgrade pip
..\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

The backend needs the ML artifacts. If `models/`, `data/ml/` or `reports/` are absent (they are git-ignored), regenerate them:

```powershell
..\.venv\Scripts\python.exe scripts\ml_prepare_data.py
..\.venv\Scripts\python.exe scripts\ml_train_dead_stock.py
..\.venv\Scripts\python.exe scripts\ml_train_forecasting.py
```

> These scripts create new timestamped model versions; they never overwrite existing ones.

---

## 3. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TREXO_OWNER_PASSCODE` | `123456789` | Owner login passcode. **Change before any shared use.** |
| `TREXO_AUTH_SECRET` | generated into `backend/data/.auth_secret` | HMAC signing secret. Set explicitly for reproducible deployments. |
| `TREXO_TOKEN_TTL_SECONDS` | `43200` (12 h) | Bearer token lifetime |
| `TREXO_ADMIN_TOKEN` | unset | Enables `POST /models/{kind}/activate`. Unset = disabled. |
| `TREXO_CORS_ORIGINS` | localhost:3000/5173 | Comma-separated allowed browser origins |
| `TREXO_DATA_DIR` | `backend/data` | SQLite and secret location |
| `TREXO_DB_PATH` | `backend/data/trexo.db` | Explicit database path |
| `TREXO_MAX_ML_RECORDS` | `20000` | ML history cap |

Frontend (`frontend/.env.local`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_USE_MOCK` | `true` | `false` selects the API |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Backend base URL |

Example backend launch with explicit secrets:

```powershell
$env:TREXO_OWNER_PASSCODE = "<strong-passcode>"
$env:TREXO_AUTH_SECRET   = "<random-64-char-secret>"
$env:TREXO_ADMIN_TOKEN   = "<random-admin-token>"
..\.venv\Scripts\python.exe -m uvicorn trexo_api.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Expected: `database = ok`, `models.status = OK`. If `models.status = unavailable`, the artifacts are missing or corrupt.

### One-time database seed

On first start the backend creates `backend/data/trexo.db`, loads `seed_data.json`, and generates the synthetic `ml_sales_history`. No manual step is required. To reset demo data:

```powershell
# after login, with the bearer token
POST /api/v1/store/reports/reset-demo
```

---

## 4. Frontend setup

```powershell
cd frontend
npm install
```

Development against the backend:

```powershell
# frontend/.env.local
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

```powershell
npm run dev      # http://127.0.0.1:5173
```

Offline demo (mock services, no backend):

```powershell
# VITE_USE_MOCK=true (default)
npm run dev
```

The mock mode uses the prototype passcode `123456789` and an in-browser store. It is intentionally **not** secure and should not be used for real data.

### Production build

```powershell
npm run lint     # tsc --noEmit
npm test         # vitest
npm run build    # emits frontend/dist
```

If `frontend/dist` exists when the backend starts, the backend mounts it at `/`, so a single process can serve both:

```powershell
npm run build
..\.venv\Scripts\python.exe -m uvicorn trexo_api.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

---

## 5. CORS and origin configuration

The frontend origin must be allowed. Defaults cover `http://localhost:5173` and `http://127.0.0.1:5173`. If you serve the built frontend from another host:

```powershell
$env:TREXO_CORS_ORIGINS = "https://store.example.com"
```

No credentials/cookies are used, so `allow_credentials` is off.

---

## 6. Operations

### Health checks

- Liveness: `GET /livez`
- Readiness: `GET /api/v1/health`

### Logs

Uvicorn standard output plus the `trexo.api` logger. Unhandled exceptions are logged with tracebacks; responses only expose a generic `INTERNAL_ERROR`.

### Backups

Back up together:

- `backend/data/` (SQLite + auth secret)
- `models/` (versioned artifacts)
- `reports/` (metrics/history)
- `data/ml/` (training inputs)

The pre-integration backup lives at `E:\TREXO-INDIA\_backups\pre_integration_20261120T174257Z`.

### Model rollback

```powershell
$token = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType 'application/json' -Body '{"password":"..."}').token

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/models/dead_stock/activate `
  -Headers @{ Authorization = "Bearer $token"; 'X-Admin-Token' = $env:TREXO_ADMIN_TOKEN } `
  -ContentType 'application/json' `
  -Body '{"version":"dead_stock-ml-1.1.0-20261119T091454Z"}'
```

The endpoint verifies the bundle checksums before repointing `LATEST`. Restart the backend after activation so cached services reload.

### Manual rollback

Stop the service, edit `models/<kind>/LATEST` to the desired existing version, restart. Never delete versions.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `MODEL_UNAVAILABLE` (503) | missing/corrupt artifacts | run the training scripts; check `models/<kind>/LATEST` |
| `MODELS status: unavailable` in health | same | as above |
| Login always 401 | passcode mismatch | check `TREXO_OWNER_PASSCODE`; restart after changing |
| CORS error in browser | origin not allowed | set `TREXO_CORS_ORIGINS` |
| `Cannot reach the TREXO backend` | backend down / wrong URL | start Uvicorn; check `VITE_API_BASE_URL` |
| `/models/{kind}/activate` → 503 `ADMIN_DISABLED` | no admin token configured | set `TREXO_ADMIN_TOKEN` and restart |
| Frontend shows demo data while API mode is on | `VITE_USE_MOCK` not `false` | fix `.env.local`, rebuild/restart |
| Database locked | multiple writers / long scan | single-node SQLite; avoid concurrent resets |

---

## 8. Production checklist (not done yet)

- [ ] Replace the demo passcode; store secrets in a secret manager.
- [ ] Terminate TLS at a reverse proxy; bind Uvicorn to loopback only.
- [ ] Add rate limiting and login lockout.
- [ ] Replace SQLite with a concurrent database if more than one instance is needed.
- [ ] Replace `LATEST` file coordination with a proper registry service.
- [ ] Connect a real POS/ledger; validate stock and cost data.
- [ ] Complete privacy/consent review for customer analytics.
- [ ] Run a pilot and measure outcomes before enabling recommendations.
- [ ] Add monitoring, alerting and log retention.
- [ ] Re-run the full test suite on the deployment target.

---

## 9. Verification commands

```powershell
# Backend
..\.venv\Scripts\python.exe -m pytest -q

# Frontend
cd frontend
npm run lint
npm test -- --run
npm run build

# Independent ML evaluation
cd ..
..\.venv\Scripts\python.exe scripts\ml_independent_evaluation.py
```

Expected at this release candidate: 141 passed / 4 skipped (Python), 27 passed (frontend), type-check and build clean, independent evaluation matching the registered metrics.
