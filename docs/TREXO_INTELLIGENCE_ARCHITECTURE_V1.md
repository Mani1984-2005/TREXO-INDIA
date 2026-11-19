# TREXO — Dead Stock Intelligence Architecture V1

**Status:** LOGICAL ARCHITECTURE PROPOSAL — nothing here is implemented.
Awaiting review.
**Principle:** dead-stock intelligence is the centre of the product;
forecasting is one optional supporting branch, never a dependency.

## 1. Design principles

1. **Detection before prediction.** Rule-based dead-stock detection must
   work with zero machine learning. Any ML component is additive and
   individually approval-gated.
2. **Evidence travels with every number.** Derived values carry lineage back
   to `SourceRow`-level transactions; scores ship their indicators.
3. **Facts ≠ derivations ≠ judgments.** Storage layers keep raw facts,
   validated facts, derived metrics, and scored judgments physically
   separate so a bad judgment can never corrupt a fact.
4. **Anomalies propagate, they don't evaporate.** Open audit anomalies
   (93 at time of writing, all `OPEN`) ride along as confidence modifiers
   rather than being filtered away.
5. **Blocked means blocked.** Components whose inputs don't exist (stock,
   cost) report unavailability instead of estimating.
6. **Read-only on sources.** The original Excel file and V1/V2 datasets are
   immutable; everything new is a new, versioned artefact.

## 2. Component catalogue

Each component lists: responsibility · inputs · outputs · key rules ·
depends on · readiness.

### C1 — Data ingestion
- **Responsibility:** bring source records in without loss or mutation.
- **Inputs:** `data/raw/Online Retail.xlsx` (today); later inventory
  snapshots, goods receipts, purchase orders, supplier master
  (`DEAD_STOCK_DATA_REQUIREMENTS_V1.md` §C).
- **Outputs:** raw landing tables keyed with `SourceRow` lineage + ingest
  manifest (file hash, row count, timestamp of the run, not of the data).
- **Key rules:** source files never written to; SHA-256 recorded; rejected
  rows kept in an error table (never dropped); one landing zone per source
  with its own schema contract.
- **Depends on:** nothing (root of the pipeline).
- **Readiness:** transaction path **ready** (proven by Audit V1);
  inventory/supplier paths **blocked on business data**.

### C2 — Data validation
- **Responsibility:** enforce quality gates and publish data-quality state.
- **Inputs:** landed tables.
- **Outputs:** validation report (row counts, coercion failures, missing
  rates, duplicates, key-typing issues, case-variant codes), per-dataset
  quality score, quarantine list.
- **Key rules:** typing contract (`StockCode` cast to text **first** —
  measured failure mode: 487,036 int rows otherwise invisible to pattern
  checks); missing values surfaced, never imputed; duplicates flagged, never
  deleted; thresholds documented per investigation 2.9 of the research doc.
- **Depends on:** C1.
- **Readiness:** **ready** (Audit V1 already implements the transaction
  gates: 25/25 checks).

### C3 — Transaction classification
- **Responsibility:** assign every row an evidence-based category,
  confidence, physical impact and manual-review state.
- **Inputs:** validated transactions; the approved rule set
  (`docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md`).
- **Outputs:** row-level classification register (14,684 entries covering
  541,909 rows), anomaly register (93 open), rule-version identifier.
- **Key rules:** ordered first-match over 25 evidence rules; UNKNOWN
  preserved; financial ≠ physical; cancellation ≠ return; first-match order
  and evidence fields exactly as approved in the policy document.
- **Depends on:** C2.
- **Readiness:** **ready (proposal pending approval)** — implemented and
  tested in the audit, but rules are *proposed* until signed off.

### C4 — Product intelligence
- **Responsibility:** per-product metrics (the measurement core of
  dead-stock detection).
- **Inputs:** classified transactions (only rows whose classification
  permits metric use — e.g. `CUSTOMER_SALE` for demand; write-offs excluded
  from demand), monthly aggregates.
- **Outputs:** product metric table at grain `product_key × period`:
  recency, frequency, velocity, trend, CV, p-zero-sale, ABC/XYZ/FSN classes,
  first/last sale, units, revenue, data-quality flags per product.
- **Key rules:** product key normalisation **only** with the approved
  normalisation policy (currently unapproved — raw key used, case variants
  kept separate and visible); metrics recompute idempotently; every metric
  stores its window and rule version.
- **Depends on:** C3 (or, for a bootstrap mode, C2 with documented caveats).
- **Readiness:** metrics **ready** (measured baseline exists: 3,898
  products, recency/frequency/ABC/FSN distributions); key-normalisation
  decision **blocked on approval**.

### C5 — Inventory state management
- **Responsibility:** hold current and historical stock positions.
- **Inputs:** inventory snapshots, goods receipts, purchase orders
  (**all missing today**).
- **Outputs:** `on_hand` series per product × warehouse × date; unit age
  layers (FIFO); open-PO positions.
- **Key rules:** snapshots are append-only with `snapshot_date`; negative
  on-hand rejected at validation; no inference of stock from sales — ever.
- **Depends on:** C1 (new ingest paths), C2 (contracts).
- **Readiness:** **blocked** (no source data). Defined now so ingestion can
  start the day a business supplies it.

### C6 — Dead-stock detection
- **Responsibility:** answer "which products are non-moving / slow-moving /
  at-risk / (with stock) dead?" using approved thresholds.
- **Inputs:** C4 metrics; C5 on-hand **when available**; threshold registry
  (method, calibration set, expiry per research doc 2.9).
- **Outputs:** detection register: `product_key, detection_type
  {NON_MOVING, SLOW_MOVING, EXCESS, AGED, DEAD_CANDIDATE},
  window, threshold_id, evidence{recency_days, invoices, units, p_zero},
  confidence, requires[...]` — with `DEAD_CANDIDATE` **only** permitted when
  on-hand evidence exists; otherwise the output is
  `HISTORICALLY_NON_MOVING` and nothing stronger.
- **Key rules:** thresholds come from the registry, never hard-coded;
  seasonal filter applied with an explicit confidence penalty (one data
  cycle); anomalies reduce confidence; detection is deterministic (same
  inputs → same register).
- **Depends on:** C4; C5 for the stronger classes.
- **Readiness:** **historical detection ready; current-dead blocked on C5.**

### C7 — Risk scoring
- **Responsibility:** compose explainable scores (families A/B/C/D).
- **Inputs:** C4 metrics, C6 detections, C5 stock, (later) C9 forecasts.
- **Outputs:** score rows with: value 0–100, family, available-mask,
  top-3 contributing indicators with raw values, limitations text, rule/
  weight version, confidence label.
- **Key rules:** missing indicators declared, never imputed; B/D refuse to
  compute without inventory/cost; equal starting weights until an approved
  back-test; every score reproducible from stored inputs.
- **Depends on:** C4, C6 (+ C5, C9 for B/C/D).
- **Readiness:** family **A ready to build**; **B/C/D blocked**.

### C8 — Financial impact analysis
- **Responsibility:** money view — capital tied up, carrying cost, excess
  value, markdown/recovery/loss estimates — strictly separated from
  historical revenue.
- **Inputs:** C5 on-hand + `unit_acquisition_cost`, holding-rate policy
  (missing today); sales revenue (available).
- **Outputs:** exposure register per product: `historical_revenue
  (fact) | inventory_value (blocked) | carrying_cost (blocked) |
  estimated_loss (blocked)` with field-level availability badges.
- **Key rules:** selling price **never** substituted for cost; blocked
  fields render as blocked, not as £0 (a zero would be a false fact);
  currency/units metadata attached.
- **Depends on:** C5, cost master.
- **Readiness:** revenue facts **ready**; all inventory-money figures
  **blocked**.

### C9 — Demand forecasting *(optional, approval-gated)*
- **Responsibility:** future demand estimates for coverage, excess and
  family-C risk.
- **Inputs:** C4 monthly series (approved calendars later).
- **Outputs:** forecast rows with horizon, method, intervals, model card.
- **Key rules:** **must not be a dependency of C6** — detection runs fully
  without it; forecasts labelled as estimates with intervals; no model
  trained to paper over unresolved data-quality issues (governance rule 14);
  each model requires its own approval before use.
- **Depends on:** C4.
- **Readiness:** **out of scope until approved** (explicitly not started).

### C10 — Recommendation engine
- **Responsibility:** turn detections into explained, reviewable actions
  (reorder hold, markdown, bundle, transfer, return, discontinue — the 11
  interventions of research doc Investigation 5).
- **Inputs:** C6/C7/C8 outputs, intervention rule definitions with
  `trigger / required_data / do_not_apply_when`, business policies.
- **Outputs:** recommendation rows: `{action, product, trigger_indicators,
  evidence_rows[], confidence, limitations[], expected_benefit_range,
  requires[], approved_by: null}`.
- **Key rules:** **no auto-execution**; every recommendation exposes why and
  what would falsify it; interventions whose required data is missing are
  listed as unavailable, not simulated; human approval recorded in the row.
- **Depends on:** C6–C8 (+ policies).
- **Readiness:** framework **design-ready**; evidence-only pilot possible
  (detection-side recommendations); value-bearing recommendations blocked on
  cost/stock.

### C11 — Reporting and dashboard APIs
- **Responsibility:** read-only, auditable access for the future UI and for
  exports.
- **Inputs:** registers from C3–C8, C10; data-quality state from C2.
- **Outputs:** paginated query APIs: executive aggregates, detection lists
  with evidence drill-down, product intelligence detail, anomaly/data-quality
  views, report exports (CSV/MD as today).
- **Key rules:** every response carries `rule_version` and `data_as_of`;
  drill-down resolves to `SourceRow` evidence; blocked capabilities are
  surfaced as `availability: blocked` (honest UI); no endpoint may mutate
  facts (reads only; approvals write to a separate audit log).
- **Depends on:** the components it reports on.
- **Readiness:** **design-ready** (backend not approved yet — see
  `TREXO_APPLICATION_ARCHITECTURE_PROPOSAL_V1.md`).

## 3. Data flow

```
                        [immutable sources]
  Online Retail.xlsx ─┐   inventory snapshots (BLOCKED) ─┐   receipts/POs (BLOCKED) ─┐
                      ▼                                  ▼                           ▼
                 C1 INGESTION ──── manifest(file hash, row counts, lineage SourceRow)
                      ▼
                 C2 VALIDATION ──── quality report, quarantine, key-typing contract
                      ▼
                 C3 CLASSIFICATION ── row categories + confidence + anomaly register (93 OPEN)
                      ▼
                 C4 PRODUCT INTELLIGENCE ── recency/frequency/velocity/trend/CV/ABC/XYZ/FSN
                      ▼                                   ▲
        ┌──────── C6 DETECTION ◄── threshold registry      │ (blocked until C5 exists)
        │             ▲                                   │
        │             │              C5 INVENTORY STATE ───┘
        │             │                   ▲
        │             │                   └── inventory/receipts/PO ingest (BLOCKED)
        │      C7 RISK SCORING (A ready · B/C/D blocked)
        │             │                ▲
        │             │                └── C9 FORECASTING (optional, approval-gated)
        │             ▼
        │      C8 FINANCIAL IMPACT (revenue facts ready · stock-money BLOCKED)
        │             ▼
        │      C10 RECOMMENDATIONS (human approval, no auto-execution)
        └──────────────► C11 REPORTING / DASHBOARD APIS (read-only, rule_version + data_as_of)
```

**Flow narrative:** facts flow downward and are never edited in place;
each layer adds provenance (`rule_version`, window, threshold_id) rather
than removing it. The **critical path for V1** is
C1 → C2 → C3 → C4 → C6 → (C7 family A) → C11: fully usable with today's
data. The **inventory branch** (C5 → C6 stronger classes → C7 B/D → C8 →
C10 value claims) attaches later without rework because its contract is
defined now. The **forecasting branch** (C9) attaches only to C7 family C
and to coverage inputs — removal of C9 leaves detection intact.

## 4. Independence from forecasting (explicit)

- Detection inputs: transaction history + thresholds + (later) stock. No
  forecast value appears in any detection rule.
- Forecast outputs may only: (a) fill family-C score inputs, (b) supply
  expected demand for coverage/excess once stock exists. They may **not**
  alter detection registers, classifications, or facts.
- If C9 is disabled or wrong, everything else keeps operating; the UI shows
  family C as `unavailable`, detection unchanged.
- Conversely, rule-based detection results must never be "corrected" by a
  model — models explain/anticipate, rules detect, humans approve.

## 5. Cross-cutting concerns

| Concern | Approach |
|---|---|
| Reproducibility | Deterministic pipelines (proved byte-identical in Audit V1); no wall-clock in outputs; versions stored as data |
| Lineage | `SourceRow` → register → metric → detection → score → recommendation |
| Quality gating | C2 gates block downstream ingest of bad batches; open anomalies surface as confidence modifiers |
| Governance | Rule/threshold/weight changes version-bump + re-run + diff + approval; UNKNOWN preserved everywhere |
| Security (future) | Read-only analytic store; approvals in an append-only audit log; no raw-source writes |
| Performance (future) | Batch daily recompute is sufficient for 0.5M-row scale; partition by period; caching at C4 metric layer |
| Extensibility | New source = new C1 contract + C2 validators; new metric = new C4 version; new intervention = C10 rule with `requires[]` |

## 6. Phased roadmap (proposal, all phases approval-gated)

| Phase | Content | Gate |
|---|---|---|
| 0 *(done)* | Audit V1, policy V1, research V1 | Review of this document set |
| 1 | Approve classification rules; build C4 metrics + C6 historical detection as offline jobs | Rule approval + threshold registry sign-off |
| 2 | Inventory/receipt/PO ingestion (C5) once business data exists | Data-sharing agreement |
| 3 | Scores B/D + C8 financial exposure | Cost/stock data validation passes |
| 4 | C9 forecasting (optional) | Separate modelling approval |
| 5 | C10 recommendations with human approval loop | UX + policy approval |
| 6 | C11 APIs + dashboard (backend/frontend) | `TREXO_APPLICATION_ARCHITECTURE_PROPOSAL_V1.md` approval |

## 7. Non-goals

No ML in detection; no rewriting of source or V1/V2 data; no removal of
ambiguous records; no generic inventory-app features unrelated to dead-stock
intelligence; no claim of current dead stock without inventory evidence.

---

**Status: Intelligence Architecture V1 proposal complete; no component
implemented, awaiting review.**
