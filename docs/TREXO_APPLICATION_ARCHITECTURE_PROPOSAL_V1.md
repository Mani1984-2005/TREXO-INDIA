# TREXO — Application Architecture Proposal V1 (Backend & Frontend)

**Status:** TECHNICAL PROPOSAL ONLY — backend and frontend are **not
approved for implementation**. This document contains no migrations, no
endpoint code, no frontend files and no mock-ups.
**Companions:** `docs/TREXO_INTELLIGENCE_ARCHITECTURE_V1.md` (logical
components this stack must host), `docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md`.

---

## Part 1 — Backend

### 1.1 Technology evaluation

| Technology | Purpose in TREXO | Suitability assessment | Risks / considerations |
|---|---|---|---|
| **Python 3.11** | Primary language: data pipelines, domain logic, API layer | **Strong fit.** The project is already Python (pandas 3.1.1, numpy 2.4.6, openpyxl 3.1.5); the audit, classification and future scoring all reuse one toolchain; one language across batch jobs and API removes translation bugs | CPU-bound pandas work needs processes (not threads); version pinning must stay in `requirements-lock.txt` |
| **FastAPI** | HTTP API layer for the dashboard and exports | **Strong fit.** Pydantic-native validation mirrors the evidence/rule contracts; automatic OpenAPI schema documents the API without a second spec; async I/O suits a read-heavy dashboard; typed responses enforce `availability: blocked` states | Async discipline needed for DB calls; do not let request handlers run heavy pandas jobs (use precomputed tables) |
| **PostgreSQL** | System of record for products, transactions, scores, recommendations, audit log | **Strong fit.** Relational model matches the entity graph; `NUMERIC` for money; partial indexes for detection lists; `JSONB` for rule-versioned evidence blobs; `tsrange`/partitioning for snapshot history; strong constraint support enforces "negative on-hand rejected" | Money requires explicit `NUMERIC(18,4)` + currency column (source currency is unlabelled — must be declared at migration time); times are naive timestamps in source (no timezone) — store + declare |
| **SQLAlchemy 2.x** | ORM / query layer with typed mappings | **Strong fit.** Declarative models keep the entity design (§1.2) executable as documentation; Alembic (when approved) gives versioned migrations; Core path available for bulk metric loads | Bulk pandas loads should use `copy()`/Core, not ORM instance inserts; keep domain logic out of ORM events |
| **Pydantic v2** | Request/response schemas, validation, discriminated unions | **Strong fit.** Exactly matches audit contracts: e.g. `ConfidenceLevel ∈ {HIGH,MEDIUM,LOW,UNKNOWN}`, `Recommendation.approved_by: None` until signed; response models can *refuse* to emit a "dead stock confirmed" state without stock evidence | Validation ≠ domain rules — keep ordered-rule logic in the domain layer |
| **pandas** | Offline metric computation (C4), batch detection (C6), scoring (C7), report generation | **Strong fit** for the 0.5M-row scale (audit runs in seconds/minutes); already proven deterministic | Never in the request path; runs as background batch writing versioned outputs |
| **Background processing** | Nightly ingest → validate → classify → metrics → detection → scores; long exports | Required for freshness without blocking the API. **Candidates:** (a) **APScheduler** — simplest, in-process cron for a single-node start; (b) **RQ/Arq + Redis** — queue with retries when jobs multiply; (c) **Celery** — full power, heavier ops; (d) **Dagster/Prefect** — pipeline orchestration, asset lineage (best long-term fit for the C1→C11 graph, more moving parts) | **Recommendation:** start with **APScheduler + an orchestrated script layer** (matches today's single-machine, no-infra reality), keep jobs behind a `PipelineRunner` interface so RQ/Dagster can replace it without touching domain code. **No package is installed by this proposal.** |
| *(Optional later)* TimescaleDB/ClickHouse | Metric/history scale-out | Not needed at current scale (34,069 product-months; 0.5M transactions) | Revisit only on measured need |

**Backend recommendation summary:** Python + FastAPI + PostgreSQL +
SQLAlchemy/Pydantic + pandas-as-batch + APScheduler-now (queue later). All
components are proven, typed, and align with the existing codebase; none
requires re-processing the source data.

### 1.2 Proposed future entities (design only — no migrations written)

```
Product            (identity & master)
  product_key PK (canonical, per approved normalisation policy)
  raw_stock_codes[]        -- pre-normalisation forms (M, m, 15056BL …)
  description, lifecycle_status {ACTIVE, DISCONTINUED, UNKNOWN},
  lifecycle_source {EVENT, INFERRED, UNKNOWN}, first_seen, last_seen
  ──< ProductMetric(period, recency_days, invoices, units, velocity,
  │                  trend_ratio, cv, p_zero, abc, xyz, fsn, rule_version)
Transaction        (fact, immutable, row-level lineage)
  transaction_id PK, source_row UNIQUE -- Excel row 2..541910
  invoice_no, stock_code_raw, description, quantity NUMERIC,
  unit_price NUMERIC, invoice_ts, customer_id NULL, country
  -- audit attributes: audit_partition, proposed_category,
  │   confidence_level, physical_impact, manual_review,
  │   classification_rule, rule_version   (from approved policy)
  -- never updated in place; corrections append with lineage
StockMovement      (typed movement events, post-approval)
  movement_id, product_key FK, movement_type
    {SALE, CANCELLATION, WRITE_OFF, ADJUSTMENT, RECEIPT, TRANSFER},
  qty, occurred_at, source_transaction_id FK NULL, warehouse_id FK NULL,
  evidence {…}, confidence
  -- rule 7: financial adjustments never stored as movements
InventorySnapshot  (blocked until business data exists)
  snapshot_date, product_key FK, warehouse_id FK,
  on_hand_qty CHECK (>= 0), average_cost NUMERIC, source_system
  UNIQUE(snapshot_date, product_key, warehouse_id)
Warehouse          warehouse_id PK, name, region
Supplier           supplier_id PK, name, default_lead_time_days,
                   moq, return_window_days, terms JSONB
PurchaseOrder      po_id PK, supplier_id FK, status, ordered_at,
                   expected_at ──< PurchaseOrderLine(product_key, qty,
                                              unit_cost, received_qty)
InventoryAgingRecord (derived at snapshot time FIFO)
  snapshot_date FK, product_key FK, age_days, qty, value
DeadStockAssessment  (the detection register — versioned, immutable)
  assessment_id, product_key FK, assessed_at, detection_type
    {NON_MOVING, SLOW_MOVING, EXCESS, AGED, DEAD_CANDIDATE},
  window, threshold_id, evidence JSONB (recency/invoices/units/p_zero),
  confidence, available_mask, requires[], rule_version,
  inventory_evidence BOOL      -- DEAD_CANDIDATE requires TRUE
RiskScore          score_id, product_key FK, family {A,B,C,D},
  score NUMERIC CHECK (0..100), top_indicators JSONB,
  limitations TEXT, weight_version, status {COMPUTED, BLOCKED, UNAVAILABLE},
  blocked_reason NULL
Recommendation     recommendation_id, product_key FK, action enum,
  trigger_indicators JSONB, evidence_rows JSONB (SourceRow refs),
  confidence, limitations[], expected_benefit_range JSONB,
  requires[], approved_by NULL, approved_at NULL, status
DataQualityReport  run_id, checks JSONB, anomalies_open INT,
  row_counts JSONB, protected_hashes JSONB, rule_version
ApprovalAuditLog   append-only: who changed which rule/threshold/weight,
  when, from_value, to_value, justification
```

**Relationships (essential):** Product 1—\* Metric/Transaction(\*)/Snapshot/
Movement/Assessment/Score/Recommendation · Supplier 1—\* PO 1—\* POLine
\*—1 Product · Warehouse 1—\* Snapshot/Movement · Transaction \*—\* Stock
Movement (via source_transaction_id, many movements can trace to one row,
e.g. cancellations) · ThresholdRegistry 1—\* DeadStockAssessment.

### 1.3 Future API surface (sketch only — not implemented)

```
GET  /api/v1/overview                  → executive aggregates + availability map
GET  /api/v1/detections?type=&page=    → detection register + evidence
GET  /api/v1/detections/{id}/evidence  → SourceRow-level drill-down
GET  /api/v1/products/{key}            → intelligence detail + history
GET  /api/v1/products/{key}/timeline   → sales/stock/score events
GET  /api/v1/scores?family=A&min=&page → explainable score rows
GET  /api/v1/exposure                  → financial view (fields may be blocked)
GET  /api/v1/recommendations?status=   → recommendations incl. approval state
POST /api/v1/recommendations/{id}/approve | /reject   → writes ApprovalAuditLog
GET  /api/v1/data-quality              → checks, open anomalies (93), gates
GET  /api/v1/reports                   → available report artefacts (read-only)
GET  /api/v1/meta/rule-versions        → active classification/threshold versions
```

Cross-cutting: cursor pagination; every response carries
`data_as_of + rule_version + availability{field: READY|BLOCKED}`; reads are
cacheable; approvals are the only writes; OpenAPI generated from Pydantic.

---

## Part 2 — Frontend

### 2.1 Technology evaluation (dashboard)

| Choice | Purpose | Assessment |
|---|---|---|
| **React + TypeScript** (Vite) | UI foundation | **Recommended.** Type contracts shared with FastAPI's generated OpenAPI client (`openapi-typescript`) make `ConfidenceLevel`, `DetectionType`, `availability` states impossible to misuse; React suits the drill-down-heavy, filter-heavy dashboard; Vite keeps tooling minimal for a dashboard (no SSR needed for an internal analytics product). Next.js adds server rendering that a data-dashboard doesn't need — revisit only if public marketing pages arrive |
| **TanStack Query** | Server state, caching, background refetch | Fits read-heavy polling dashboard; keeps "blocked" states explicit in query results; avoids global-store sprawl |
| **TanStack Table** | Large detection/product tables | Headless: sorting/filtering/pagination for 3,898 products without bespoke code; virtualisation available if needed |
| **Charts: Recharts *or* Apache ECharts** | Trend, recency distribution, exposure charts | Recharts: simplest React-native API, good for standard charts. ECharts: stronger for large scatter/tree maps (product scatter of recency × revenue). **Pick one** — recommend starting with Recharts, escalate if visual demands grow |
| **Styling: Tailwind + a headless component set (Radix/shadcn-style)** | Consistent accessible UI | Fast to build dense, accessible (keyboard/ARIA) analytics UI; avoids heavy framework lock-in |
| **Zod (client-side) + generated types** | Runtime validation of API payloads | Defence-in-depth alongside Pydantic; version mismatches surface as visible errors instead of broken UI |

Not recommended now: SSR frameworks, Redux (TanStack Query covers server
state), micro-frontends (single team, single app).

### 2.2 Proposed dashboard sections (design — no files created)

| # | Section | What it shows | Key widgets | Honest-state handling |
|---|---|---|---|---|
| 1 | **Executive Overview** | Portfolio health at a glance | KPI strip: products tracked, % sold in last 30d (measured 75.04%), historically non-moving count (460 >180d), open anomalies (93), data-as-of badge, rule version | Financial KPIs render "Requires cost data" chips — never £0 |
| 2 | **Dead Stock Overview** | Products confirmed (or candidate) dead **with stock evidence** | Table filtered by detection type; ageing chart; on-hand value column | Without inventory data the page shows the *blocked* banner listing the exact missing inputs (on_hand, cost) + the historical non-moving view as substitute, clearly relabelled |
| 3 | **Slow-Moving Products** | Slow movers by FSN/velocity/frequency | Sortable table: recency, invoices, velocity, trend arrow, FSN class, threshold id | Threshold chips open a popover showing method + calibration + expiry (research 2.9) |
| 4 | **At-Risk Inventory** | Risk family A now; B/C when available | Score list 0–100, expandable indicator breakdown (top-3 + raw values + available-mask) | Family badges A/B/C/D with status (COMPUTED/BLOCKED); unavailable families grey out with reason |
| 5 | **Financial Exposure** | Money at stake | Historical revenue facts; inventory value/carrying cost/loss panels | Each panel carries its own availability state; source currency declared (TBC) with a footnote that historical revenue ≠ capital at risk |
| 6 | **Product-Level Intelligence** | Single product deep dive | Sales timeline, monthly demand bars, invoice list with `SourceRow` links, classification of each row, anomalies touching the product, metrics with windows | Row-level evidence panel reproduces the audit's evidence/contradiction text verbatim |
| 7 | **Recovery Recommendations** | Actions with explanations | Cards: action, trigger indicators, evidence, expected-benefit range, `requires[]`, limitations, do-not-apply conditions, Approve/Reject buttons writing the audit log | Everything shows `approved_by: null` until a human acts; actions needing missing data are listed under "unavailable actions" with the missing fields named |
| 8 | **Demand Intelligence** | Demand patterns (no ML until approved) | Monthly/weekly trends, ABC/XYZ/FSN matrices, seasonality observed-in-one-cycle caveat badge, intermittency/zero-demand views | Forecast panel absent/disabled with "modelling not approved" note — no placeholder charts that imply forecasts exist |
| 9 | **Reports & Data Quality** | Trust layer | Generated report artefacts (audit MD/CSVs downloadable), validation checks 25/25, open anomaly list (93 with severity), protected-file hashes, rule versions | Anomalies are visible, filterable, and linked to affected products — quality problems are shown, not hidden |

**UI-wide explainability contract:** every number exposes
`(value, window, rule_version, evidence link)` on click; blocked states name
their missing fields; nothing renders a zero where the truth is "unknown".

---

## Part 3 — Explicit non-compliance with implementation

As required by the assignment: **no database migrations, no API endpoints,
no frontend files, no components, no mock data** were created. This document
is prose and tables only. Implementation requires the final approval gate.

## Part 4 — Open questions for review

1. Backend: is the APScheduler-first (queue-later) processing choice
   acceptable for Phase 1?
2. Data store: single PostgreSQL for facts + JSONB evidence, or split
   analytical store later (default: single DB until measured need)?
3. Frontend: React+Vite with Recharts confirmed, or mandate ECharts now?
4. Auth: none for an internal Phase 1, or SSO from the start?
5. Currency: source data labels no currency (UK retailer ⇒ likely GBP) —
   who confirms the reporting currency before any money figure is displayed?
6. Which dashboard sections may ship if only Phase-1 (sales-side) data
   exists? (Recommended: 1, 3, 4A, 6, 9 fully; 2, 5, 7, 8 in blocked-state
   form.)

---

**Status: Application Architecture Proposal V1 complete; backend/frontend
NOT implemented, awaiting review.**
