# TREXO-INDIA Phase B Completion Report

**Branch:** `remediation/critical-release-fixes`  
**Baseline:** `6f9ce44`  
**Date:** 2026-11-20  
**Status:** Phase B implementation and verification complete.

## 1. Findings corrected

### AUD-001 — inventory overselling

**Root cause:** repeated sale lines were validated and decremented from the same original product snapshot. Each line's stock write could overwrite the previous write.

**Correction:** sale lines are aggregated by `productId`; aggregate quantity is validated against one product row inside `BEGIN IMMEDIATE`. Stock is written once per distinct product.

**Regression evidence:**

- repeated lines 3 + 4 charge quantity 7 and decrement stock by exactly 7;
- a request exceeding available stock is rejected with `INSUFFICIENT_STOCK`;
- failed requests leave stock unchanged.

### AUD-002 — concurrent sales

**Root cause:** separate read-modify-write operations used different transactions for stock, invoice sequence and UPI references.

**Correction:** complete sale writes use one `StoreDB.transaction()` connection, SQLite `BEGIN IMMEDIATE`, WAL journal mode and a 15-second busy timeout. Invoice sequence and confirmed UPI references are updated in the same transaction.

**Regression evidence:**

- concurrent duplicate UPI tests pass;
- concurrent stock tests pass;
- unique invoices are generated.

### AUD-003 — transaction atomicity

**Root cause:** `put()`, `set_meta()` and history writes opened independent connections and committed separately.

**Correction:** sale, customer, stock, sales, history and metadata writes execute inside one explicit transaction and commit once. A service exception or database exception rolls back the transaction.

**Regression evidence:** a database transaction rollback test verifies a partial insert is absent after an exception.

### AUD-004 — transactional documentation

**Correction:** deployment documentation now distinguishes the explicit owner/admin credential variables and no longer presents an insecure universal owner passcode.

### AUD-005 — demo reset authorization

**Root cause:** reset was accessible with an owner bearer token and no confirmation body.

**Correction:** reset now requires `require_admin`, a valid `X-Admin-Token`, and the exact body `{"confirmation":"RESET-DEMO"}`. Invalid confirmation and successful reset attempts are logged without credentials.

**Regression evidence:**

- unauthenticated reset returns 401;
- owner-only reset returns 403;
- wrong admin credential returns 403;
- invalid confirmation returns 400;
- valid confirmation returns 200.

### AUD-006/AUD-007 — insecure credentials

**Root cause:** the owner passcode defaulted to `123456789`, and frontend mock code/test content preserved the prototype credential.

**Correction:**

- removed the universal owner-passcode default;
- added explicit `TREXO_OWNER_PASSCODE` configuration;
- added preferred `TREXO_OWNER_PASSCODE_HASH` support using PBKDF2-SHA256;
- removed frontend prototype-password authentication logic;
- the API reset service sends explicit confirmation;
- frontend build output was rebuilt and scanned for the former credential;
  strict source and bundle review found no hardcoded prototype-password assignment or test credential constant in executable source. The exact digit substring also occurs coincidentally inside QR/charset constants and generated token-character strings; those contexts are not credential assignments.

## 2. Database transaction strategy

- SQLite WAL mode is enabled on database initialization.
- `busy_timeout` is set to 15 seconds.
- Sale operations use `BEGIN IMMEDIATE`.
- `StoreDB.transaction()` owns the connection, commit and rollback.
- Existing `_lock` remains as a per-process guard; SQLite write locking handles cross-thread/cross-process boundary behavior.

## 3. Exact files changed

Backend:

- `backend/trexo_api/store/db.py`
- `backend/trexo_api/store/service.py`
- `backend/trexo_api/config.py`
- `backend/trexo_api/security.py`
- `backend/trexo_api/schemas/domain.py`
- `backend/trexo_api/routers/store.py`

Tests:

- `backend/tests/conftest.py`
- `backend/tests/test_health_auth.py`
- `backend/tests/test_store_api.py`

Frontend:

- `frontend/src/services/authService.ts`
- `frontend/src/services/authService.test.ts`
- `frontend/src/services/apiServices.ts`

Documentation:

- `docs/TREXO_DEPLOYMENT_GUIDE.md`

No source outside this remediation scope was changed.

## 4. Credential provisioning strategy

Deployments must set `TREXO_OWNER_PASSCODE` or `TREXO_OWNER_PASSCODE_HASH`, plus `TREXO_AUTH_SECRET` and `TREXO_ADMIN_TOKEN`.

The preferred passcode format is an environment-only PBKDF2-SHA256 hash. Secrets must not be checked into source or logs.

Mock mode must not contain any production credential or protect real data.

## 5. Test evidence

| Suite | Result |
|---|---|
| Targeted store/auth tests | 30 passed |
| Backend tests | 44 passed |
| Frontend unit tests | 27 passed |
| Full existing suite | 104 passed, 4 skipped |
| Full slow-dataset suite (`TREXO_SLOW_TESTS=1`) | 108 passed |
| Frontend build | successful |
| `git diff --check` | passed |

## 6. Protected-file integrity

Verified SHA-256 values:

| Protected file | SHA-256 |
|---|---|
| `data/raw/Online Retail.xlsx` | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| `data/ml/valid_sales_v1.csv.gz` | `d046968b112722ac5a26d9ba7f495913d4d9b045db228535e4b79de8b7b749e2` |
| `data/ml/data_manifest_v1.json` | `d892893f40fef4558b4a56af497950b7d24a7853d75c5fc75e15d4bcdffe986f` |

All model `.joblib` artifact hashes matched their registered metadata/checksum evidence. No dataset, model artifact, rejected challenger or D01 governance decision was modified.

## 7. Original defect reproduction

Before remediation:

- repeated 3 + 4 lines charged 7 units but left stock at 10 from 14;
- owner-only reset returned 200.

After remediation:

- repeated 3 + 4 lines decrement stock by exactly 7;
- insufficient-stock requests leave stock unchanged;
- owner-only reset is forbidden.

## 8. Outstanding risks

- Login throttling/lockout is not yet implemented.
- No persistent audit record for reset exists; only structured process logs.
- SQLite remains constrained to a single-process/single-worker deployment model unless a client/server database is approved.
- Reset remains destructive even when authorized; it should remain demo-mode only and backed up.
- The frontend mock mode is not suitable for real data.
- Model cache invalidation, package exposure and full independent security review remain separate from this Phase B scope.

## 9. Phase classification

- AUD-001: **FIXED AND VERIFIED**
- AUD-002: **FIXED AND VERIFIED**
- AUD-003: **FIXED AND VERIFIED**
- AUD-004: **FIXED AND VERIFIED**
- AUD-005: **FIXED AND VERIFIED**
- AUD-006: **FIXED AND VERIFIED** for removal of insecure default; rate limiting remains open
- AUD-007: **FIXED AND VERIFIED** for source/build credential removal

No deployment, commit, push, merge or model activation was performed. Phase B stops here pending independent review.
