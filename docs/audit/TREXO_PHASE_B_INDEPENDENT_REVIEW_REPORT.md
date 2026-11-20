# TREXO-INDIA Phase B Independent Red-Team Review

**Branch:** `remediation/critical-release-fixes`  
**Baseline:** `6f9ce44`  
**Review date:** 2026-11-20  
**Scope:** Independent review only. No application code, tests, datasets, models or protected artifacts were modified.

## 1. Executive assessment

Phase B fixes the original in-request repeated-line defect, the core sale transaction boundary and UPI-reference deduplication. The reset endpoint is also no longer accessible to an owner bearer token alone.

The implementation is **not fully release-ready**.

Major remaining issues:

- Cash or non-UPI sale retries have no idempotency key and can create duplicate sales.
- Stock updates through product patch, stock adjustment and supplier-return endpoints are separate read-modify-write operations. They can race with the sale transaction and overwrite a transactionally decremented stock balance.
- Reset audit trail exists only in process logs, not in persistent database records.
- Login throttling/lockout is absent.
- Credential provisioning is external to the application; no salt-generation/provisioning utility or startup validation is implemented.
- The frontend API reset workflow does not provide the required admin header, so API-mode reset cannot be initiated by the current frontend UI.

Overall classification:

| Area | Classification |
|---|---|
| Repeated product-line accounting | VERIFIED FIXED |
| Sale transaction boundary | VERIFIED FIXED for the sale path |
| Concurrent sales for `complete_sale` | VERIFIED FIXED |
| UPI duplicate protection | VERIFIED FIXED |
| Negative inventory through alternate endpoints | VERIFIED FIXED against direct negative values |
| Cross-endpoint stale stock writes | NOT FIXED |
| Cash/non-UPI duplicate retry | NOT FIXED |
| Reset authorization | VERIFIED FIXED |
| Default passcode removal | VERIFIED FIXED |
| PBKDF2 hash verification | PARTIALLY VERIFIED |
| Token expiration/signature verification | VERIFIED FIXED |
| Login throttling | NOT FIXED |
| Persistent reset audit | NOT FIXED |
| Database rollback primitive | PARTIALLY VERIFIED |
| Test adequacy | PARTIALLY VERIFIED |

## 2. Original defects and reproduction

### Original repeated 3 + 4 defect

Reproduced after remediation in an isolated temporary SQLite database with stock 14:

- `POST /api/v1/store/sales`
- lines: quantity 3 and quantity 4
- payment: cash
- response: 201
- charged quantity: 7
- stock after sale: 7

This demonstrates that the original behavior is corrected: both lines contribute to an aggregate quantity of 7 and stock decreases by exactly 7.

With stock 5, the original aggregate is rejected before mutation with HTTP 400 and stock remains 5.

### Concurrency reproduction

An isolated 20-thread probe used one stock product and one quantity per cash sale:

- accepted sales: 5
- rejected as insufficient stock: 15
- final stock: 0
- no negative stock or oversell was observed

The core `complete_sale` path is safe under the tested same-process threaded workload.

### Duplicate UPI reproduction

Existing tests and transaction code confirm that a UPI reference already in `confirmed_refs` is rejected with `DUPLICATE_UPI_REF`/409. The reference is written into the same sale transaction.

### Cash retry reproduction

Identical cash sale payload repeated twice, with no UPI reference, returned 201 twice and created two different sale IDs. Therefore duplicate processing is not universally fixed.

### Reset reproduction

In an isolated database:

- unauthenticated reset: 401;
- owner bearer with no admin token: 403;
- wrong admin token: 403;
- exact confirmation with valid owner bearer and admin token: 200;
- wrong confirmation: 400.

## 3. File-by-file code review

### `backend/trexo_api/store/service.py`

The sale path aggregates quantities in a local dictionary and uses `BEGIN IMMEDIATE` through `StoreDB.transaction()`.

Positive findings:

- repeated product lines are coalesced;
- aggregate quantity is compared with the transaction-time stock row;
- stock is updated once per product;
- sale, customer, stock, invoice sequence, UPI reference and ML history are written in the same transaction;
- duplicate UPI references are checked inside the transaction;
- explicit application-level insufficient-stock errors prevent mutation.

Remaining findings:

- no idempotency key exists for cash, Udhaar or retried sales;
- the method reads and writes only sale entities under one transaction, but alternate product mutation methods do not participate in the sale transaction;
- ML history and the sale share the invoice number in the same transaction;
- `_add_history()` and old invoice helpers are no longer on the new sale path, but remain available to other paths and can be misleading.

### `backend/trexo_api/store/db.py`

Positive findings:

- `transaction()` uses `BEGIN IMMEDIATE`;
- busy timeout is set to 15 seconds;
- commit and rollback surround the yielded connection;
- WAL mode is enabled during database initialization;
- `sqlite3.Connection` lifecycle is explicit and closes in `finally`.

Remaining findings:

- `_lock` is process-local and does not protect separate application processes;
- SQLite serializes writers across processes, but ordinary `connection()` read-modify-write methods remain vulnerable to stale snapshots;
- reset clearing and reseeding are not one whole operation;
- no migration framework or schema versioning exists.

### `backend/trexo_api/routers/store.py`

The reset route now:

- is under the router's global `require_auth` dependency;
- has `require_admin`;
- requires an exact confirmation body.

The implementation is server-side and does not rely on frontend authorization.

The API implementation still has no persistent reset audit table. It logs only success/rejection text.

The frontend API reset implementation does not attach `X-Admin-Token`; therefore the current frontend cannot provide a valid API-mode admin reset.

### `backend/trexo_api/security.py`

Positive findings:

- bearer signatures are HMAC checked before payload decoding;
- exp is verified;
- admin token is compared with `hmac.compare_digest`;
- owner passcode is not compared with `==`;
- hashed passcode verification uses `hmac.compare_digest`.

Remaining findings:

- no login throttling or lockout;
- no token revocation, JTI or server-side session;
- no `iat`, `aud` or issuer claim;
- malformed signed exp values can raise `ValueError` from `int(data["exp"])` without conversion to `ApiError`;
- no admin role is embedded in the bearer token;
- static `TREXO_ADMIN_TOKEN` is the only admin authorization mechanism.

### `backend/trexo_api/config.py`

Positive findings:

- no universal owner-passcode default remains;
- `TREXO_OWNER_PASSCODE_HASH` is supported;
- `TREXO_AUTH_SECRET` uses an environment secret or random 48-byte file fallback;
- `TREXO_ADMIN_TOKEN` has no default.

Remaining findings:

- no startup enforcement requires owner/admin credentials;
- no in-repository salt-generation command or provisioning utility exists;
- the PBKDF2 iteration count is not validated for a minimum or maximum;
- the plain owner-passcode environment variable stores plaintext credentials;
- the random auth-secret file is a good local fallback but not a production secret-management mechanism.

### `frontend/src/services/authService.ts` and `apiServices.ts`

Mock mode no longer accepts the former prototype password.

API login sends the passcode to the backend and stores only the bearer token.

API reset sends `RESET-DEMO` but does not attach `X-Admin-Token`. No admin token is intentionally exposed in frontend source/bundle.

## 4. Inventory concurrency analysis

### Core sale transactions

The core sale implementation is correct under a same-database, SQLite-writer workload:

- `BEGIN IMMEDIATE` obtains the writer lock;
- product, invoice, UPI, history and sale writes occur in the same transaction;
- stock is aggregated;
- insufficient stock is checked before mutations.

### Alternate endpoint stale-write finding

`adjust_stock`, `update_product` and `return_to_supplier` calculate a stock value from a product read and later call `db.put()` in separate connections. They do not hold a transaction across read and write.

Examples:

- `update_product()` reads stock and patches product fields at [service.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/service.py:222).
- `adjust_stock()` reads stock and writes `stock + delta` at [service.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/service.py:426).
- `return_to_supplier()` reads stock and writes the decremented value at [service.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/service.py:432).
- sale decrement is transactionally isolated at [service.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/service.py:253).

An alternate endpoint can read stock 10, a sale can commit a decrement to 5, and the stale alternate endpoint can write 10 or 12 back. This can resurrect stock or lose accounting updates even though direct negative stock is prevented.

Classification: **NEW FINDING / HIGH**.

### Negative inventory

Negative inventory is prevented through:

- Pydantic `stock_qty >= 0`;
- service patch `max(0, ...)`;
- adjust-stock `max(0, ...)`;
- supplier-return clamping;
- sale aggregate validation.

No direct negative path was found. Negative stock is therefore fixed at the visible API boundaries.

## 5. Authorization analysis

`/api/v1/store/reports/reset-demo` is not controlled by the frontend. It is protected by:

1. bearer token verification;
2. `TREXO_ADMIN_TOKEN` verification;
3. exact confirmation text.

This is authentication plus authorization, not an unintended two-person approval workflow. It does not require two human approvers or two signatures; it requires one valid owner bearer session and one configured administrator token.

However, it is a shared-secret admin mechanism, not a role or admin identity. Anyone holding both values has admin capability. Owner tokens themselves carry only `sub=owner`.

Admin access through the current frontend is not implemented because the frontend has no administrator-token field and deliberately should not embed one. Direct API access can succeed when the caller supplies the secret header.

## 6. Credential security analysis

### Universal default

No universal owner passcode remains in source or executable backend logic.

### PBKDF2 implementation

The hash format is parsed correctly for `pbkdf2_sha256$iterations$salt$hash`. Verification uses constant-time comparison.

Gaps:

- no salt-generation utility;
- no provisioning script;
- no minimum iteration check;
- no digest/salt length check;
- no rejection of absurd iteration counts;
- no startup report of misconfiguration.

This is an operator-configurable hash verifier rather than a complete credential provisioning system.

### Salt

The salt is external configuration when `TREXO_OWNER_PASSCODE_HASH` is supplied. It is not stored or generated by the application. Salt secrecy is unnecessary, but a provisioning workflow is needed to prevent low-quality operatorsupplied salts or weak iterations.

### Token security

The implementation correctly rejects:

- malformed tokens;
- invalid signatures;
- expired tokens.

It does not revoke or persist sessions. A stolen unexpired token remains valid. Logout is only browser-side.

### Secret exposure

No passcode or token signing secret is intentionally returned by login or health endpoints. The frontend source no longer contains the former prototype passcode. Admin and auth secrets are not included in the frontend API client.

## 7. Database integrity analysis

### Rollback

The `transaction()` context manager rolls back on any exception from the yielded block. The existing rollback test confirms a manually inserted marker is absent after an exception.

Fault injection at every important sale write stage is not present. Therefore rollback is **PARTIALLY VERIFIED**, not comprehensively verified.

### WAL and locking

WAL and a 15-second busy timeout are persistent/present:

- [db.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/db.py:43)
- [db.py](/E:/TREXO-INDIA/TREXO-INDIA-ML/TREXO-INDIA/backend/trexo_api/store/db.py:64)

The sale transaction is appropriate for SQLite cross-thread and cross-process writer serialization.

### Application restart

The database is persisted to the configured SQLite file. WAL mode and the standard transaction commit should survive restart. No destructive operation was performed.

### Multi-process behaviour

SQLite `BEGIN IMMEDIATE` serializes sale writers across processes. However, stale read-modify-write methods still exist on alternate endpoints and are not converted to an atomic transaction.

### Migration compatibility

No schema migration framework exists. The added reset schema field and transaction methods do not require migration. Future document shape changes remain dependent on application writes and no schema versioning.

## 8. Test quality assessment

### Tests that detect the original defect

`test_repeated_product_lines_aggregate_without_overselling` asserts aggregate stock decrement. `test_repeated_product_lines_reject_when_aggregate_exceeds_stock` asserts insufficient stock and no mutation.

These tests would fail under the original implementation because the original returned success and stock decrements may not match the charged quantity.

### Tests that detect concurrency

The concurrent tests use multiple threads and assert stock, invoice uniqueness and UPI deduplication.

The same-product concurrency test has enough stock for all requests and verifies exact decrement and unique invoices. It does not deliberately test oversell when the requested quantity exceeds available stock across threads.

### Missing edge cases

- identical cash retry/idempotency key;
- sale retry after success but response lost;
- stock adjustment concurrent with sale;
- product patch concurrent with sale;
- supplier return concurrent with sale;
- fault injection after product write, customer write, sale write, history write and UPI/meta write;
- cross-process SQLite races;
- forged/malformed signed token exp;
- admin token alone;
- expired owner/admin operation;
- reset confirmation bypass and persistent audit;
- low/empty/absurd PBKDF2 iterations and malformed hashes;
- restart/recovery after interrupted reset or sale;
- reset concurrency with active writes.

## 9. Remaining vulnerabilities

| Severity | Finding | Classification |
|---|---|---|
| 🟠 HIGH | Cash/non-UPI sale retries create duplicate financial records | NEW FINDING |
| 🟠 HIGH | Alternate inventory endpoints use stale read-modify-write and can overwrite sale decrements | NEW FINDING |
| 🟡 MEDIUM | No login throttling or lockout | NOT FIXED |
| 🟡 MEDIUM | Reset audit is not persistent | NOT FIXED |
| 🟡 MEDIUM | No complete credential provisioning or startup policy | NOT FIXED |
| 🟡 MEDIUM | No persistent token revocation | NOT FIXED |
| 🟡 MEDIUM | Reset is not exposed to the frontend with an admin credential | NOT TESTED / UI mismatch |
| 🟡 MEDIUM | Reset and seed are separate database operations | NEW FINDING |
| ⚪ LOW | Malformed signed exp claim can raise `ValueError` rather than an auth error | NEW FINDING |
| ⚪ LOW | No migration/schema version strategy | NOT FIXED |

## 10. Recommended corrections

1. Add an idempotency key or client request ID to sales and enforce a unique constraint for it.
2. Add UPI duplicate protection as one transaction alongside all other sale processing; repeat behavior should use the idempotency key for every payment method.
3. Convert product patch, stock adjustment and supplier return mutations to `BEGIN IMMEDIATE` read/write transactions or provide SQL conditional stock updates.
4. Replace stale product JSON reads with service-level stock operations that check and update the live balance in the same transaction.
5. Add cross-endpoint concurrency tests and stale-stock overwrite tests.
6. Add fault injection tests for every sale write stage and verify rollback of product, customer, sale, history and metadata changes.
7. Add login attempt throttling, lockout and failure auditing.
8. Add an append-only or database-backed reset audit record, including actor identity and outcome.
9. Add a credential provisioning script that generates a cryptographically random salt and PBKDF2 hash, without printing the secret or hash. Enforce iteration minimum.
10. Add startup configuration validation and fail closed for production deployments missing owner/admin/auth credentials.
11. Add a frontend administrator workflow only with an explicit deployment policy; do not place `TREXO_ADMIN_TOKEN` in browser source.
12. Make reset clearing and reseeding one transaction or mark/reset a demo database only.
13. Convert malformed signed exp claims to `TOKEN_INVALID_CLAIMS`.
14. If real identity is required, replace the shared static admin token with a separate server-side admin role and credential.

## 11. Release recommendation

**Release is NOT READY.**

The core Phase B repeated-line, sale-concurrency and reset authorization fixes are verified. However, duplicate cash sales and stale cross-endpoint stock mutations leave data-integrity gaps that can occur outside the exact original defect.

Login throttling, persistent reset audit, credential provisioning and stale write protection remain unresolved. No deployment or pilot should be approved until the HIGH findings are corrected and independently retested.
