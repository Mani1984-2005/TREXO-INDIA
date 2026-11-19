# TREXO-INDIA — GOVERNANCE POLICY PROPOSALS V1

**Document ID:** `TREXO-GOVERNANCE-POLICY-PROPOSALS-V1`
**Version:** V1
**Status:** `READY_FOR_OWNER_REVIEW` — proposals only; nothing approved
**Scope:** Stage 2 governance design for the dead-stock intelligence foundation
**Implementation:** none. This document creates no rule, script, dataset or configuration.

---

## 1. Purpose and how to read this document

This document turns the seven open decisions in `TREXO_APPROVAL_REVIEW_PACK_V1.md` into
proposed policies and a proposed dead-stock definition set. It exists so that the project
owner can approve, reject, modify or defer a *rule* once, rather than re-deciding the same
question in every future script.

Every policy below is written in three explicitly separated states:

| State | Meaning | Where it appears |
|---|---|---|
| **EXISTING** | What the current code and artefacts actually do today | Stated as fact, verified against the repository |
| **PROPOSED** | What this document recommends | Clearly labelled; **not in force** |
| **APPROVED** | What the owner has explicitly authorised | **Empty everywhere** — no approval has been given |

A policy becomes binding only when the owner completes §13 and the approval is recorded in the
master tracker. Until then the existing behaviour continues unchanged.

---

## 2. Governance invariants

These are not policies to be voted on; they are constraints any approved policy must satisfy.

1. The raw workbook is immutable. Every derived row keeps a `SourceRow` reference.
2. Financial impact and physical movement are independent dimensions. One field never carries
   both meanings.
3. Transaction sign is evidence, not classification.
4. Zero price does not imply zero physical movement.
5. `UNKNOWN` is a legal, permanent state. It may not be forced or auto-resolved.
6. No source row is deleted, rewritten or excluded destructively. Exclusion is an analytical
   view over an intact ledger.
7. Product identity merges are reversible and evidence-based.
8. Historical sales inactivity is never reported as current dead stock.
9. Every rule change is versioned, tested, reconciled and diffed before release.
10. No rule is implemented before the owner approves it; no approval is inferred from silence.

---

## 3. Policy 1 — Transaction classification

### 3.1 EXISTING

- `docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md` defines 25 ordered, first-match evidence
  rules over eight audit partitions (P01–P08).
- The register (`reports/transaction_classification_register_v1.csv`) contains 14,684 entries
  (14,682 ROW + 2 GROUP) covering 541,909 source rows exactly once.
- Categories in use: CANCELLATION 8,704; SHIPPING_CHARGE 2,110; NEEDS_MANUAL_REVIEW 1,581;
  UNKNOWN 1,439; CUSTOMER_SALE 500 row-level + 527,225 group-covered; PHYSICAL_STOCK_MOVEMENT
  179; SERVICE_CHARGE 87; FINANCIAL_ADJUSTMENT 84.
- Nothing is approved; every entry is `PROPOSED_*`.

### 3.2 PROPOSED

**P1.1** Adopt the three-dimension model: business event, financial impact, physical impact.

| Dimension | Allowed values (proposal) |
|---|---|
| Business event | SALE, CANCELLATION, CUSTOMER_RETURN, WRITE_OFF, STOCK_CORRECTION, PROMOTION, SAMPLE, SERVICE, FINANCIAL_ADJUSTMENT, UNKNOWN |
| Financial impact | REVENUE_POSITIVE, REVENUE_REVERSAL, ZERO_FINANCIAL_VALUE, NON_PRODUCT_CHARGE, NON_PRODUCT_ADJUSTMENT, UNKNOWN |
| Physical impact | STOCK_DECREASE, STOCK_INCREASE, NO_MOVEMENT, UNKNOWN |

**P1.2** Keep the ordered first-match evidence rules as the deterministic core. A later rule
may not override an earlier one; changes require a policy version bump.

**P1.3** A row may be `UNKNOWN` in one dimension and known in another (e.g. zero revenue,
unknown physical impact). Downstream reports must state which dimension they consume.

**P1.4** `D01`–`D07` outcomes become rule inputs, not ad-hoc exceptions. Each rule carries the
decision ID that authorised it.

### 3.3 APPROVED

_None._

---

## 4. Policy 2 — Product identity and aliases

### 4.1 EXISTING

- Raw `StockCode` is mixed-type: 487,036 integers, 54,873 strings.
- V2 keeps case variants separate: `15056BL` and `15056bl` are two product rows.
- 4,070 raw codes; 3,958 after strip+upper; 112 case-collision keys.
- No alias table, no product master, no canonical identifier in any artefact.
- `ANOM-0036` (case variants) is `OPEN`.

### 4.2 PROPOSED

**P2.1** Processing order: cast to string → strip whitespace → preserve original → derive
canonical key. The original is never overwritten.

**P2.2** Default canonicalization is `strip` + `upper`. It is *not* applied as a merge until
each collision is reviewed, because 650 codes already carry more than one description.

**P2.3** A governed alias table records: original code, canonical code, product description(s),
evidence for the merge, approver, approval date, effective dataset version.

**P2.4** Merge evidence hierarchy: (a) identical description + compatible price/unit pattern;
(b) product master or supplier confirmation; (c) owner decision. Code similarity alone is
insufficient.

**P2.5** Family codes (`GIFT_*`, `DCGS*`) are never collapsed into a family key for product
identity; each code is its own identity until evidence says otherwise.

**P2.6** `15056BL` and `15056bl` are proposed as one physical product (description
"EDWARDIAN PARASOL BLACK"; 2,844 units sold). This is the reference case for P2.4(a).

### 4.3 APPROVED

_None._

---

## 5. Policy 3 — Financial adjustments

### 5.1 EXISTING

- V2 includes any row meeting: no `C` prefix, quantity > 0, unit price > 0.
- This admits the bad-debt positive row (+£11,062.06 on A563185) as product revenue while
  excluding its two negative-price counterparts.
- Financial codes `B`, `D`, `AMAZONFEE`, `BANK CHARGES`, `CRUK` are not consistently separated.

### 5.2 PROPOSED

**P3.1** A financial adjustment is any row whose purpose is an accounting posting rather than
merchandise supply. Initial membership: `B` (bad debt), `D` (discount), `AMAZONFEE`,
`BANK CHARGES`, `CRUK`.

**P3.2** Financial adjustments are excluded from product sales, product movement and any
per-product demand metric.

**P3.3** They are retained in a financial-adjustment view that preserves the invoice group and
its **net** value. For A563185–A563187 the net is **−£11,062.06**, not zero.

**P3.4** Reconciliation identity: `product revenue + financial adjustments = total accounting
revenue`. Any report that breaks this identity is defective.

**P3.5** No adjustment may be deleted. An adjustment may be reclassified only with evidence and
an audit record.

### 5.3 APPROVED

_None._

---

## 6. Policy 4 — Physical movement

### 6.1 EXISTING

- Physical impact is a register column with values `PHYSICAL_STOCK_DECREASE` (679),
  `NO_PHYSICAL_STOCK_MOVEMENT` (2,200) and `UNKNOWN_PHYSICAL_IMPACT` (11,805).
- No stock ledger exists; physical impact is inferred from transaction evidence only.

### 6.2 PROPOSED

**P4.1** Physical impact may be asserted only from evidence of goods movement: a stock
movement record, a despatch/receipt document, or an explicit business confirmation. Transaction
sign and price are supporting evidence, never sufficient alone.

**P4.2** The default for unresolved rows is `UNKNOWN`. `NO_MOVEMENT` requires positive evidence
that the row is financial or administrative.

**P4.3** A cancellation is not a stock increase unless a returns record exists. A zero-price
line is not zero movement unless the line is financial/administrative.

**P4.4** Physical movement is never valued with selling price. Valuation requires acquisition
cost (currently absent).

**P4.5** When real inventory data arrives, the stock ledger becomes authoritative for physical
movement; transaction-derived physical impact becomes a cross-check, not the source of truth.

### 6.3 APPROVED

_None._

---

## 7. Policy 5 — Duplicate investigation

### 7.1 EXISTING

- 5,268 extra rows in 4,879 exact-duplicate groups on the eight source columns.
- Duplicates remain in V2; `ANOM-0027` is `OPEN`.
- No duplicate flag exists in the register schema.

### 7.2 PROPOSED

**P5.1** No deletion. Every row is preserved with its `SourceRow`.

**P5.2** Add a `duplicate_candidate` flag plus `duplicate_group_id` and `group_size`, computed
with the eight-column key and recomputed deterministically on every run.

**P5.3** A deduplicated analytical view may be produced only after the owner approves a business
key. Until then, both gross and candidate-adjusted measures may be shown, clearly labelled.

**P5.4** Cancellation/reversal pairs are not duplicates: they differ by invoice and sign. The
key must never drop `InvoiceNo` or `InvoiceDate`.

**P5.5** A row confirmed as a legitimate repeat line is marked `NOT_DUPLICATE` with evidence;
the flag is not removed from history.

### 7.3 APPROVED

_None._

---

## 8. Policy 6 — Zero-price movement

### 8.1 EXISTING

- 2,515 zero-price rows: 1,179 positive (+72,603 units), 1,336 negative (−206,957 units).
- All are excluded from V2 by the price > 0 rule.
- 1,287 of 1,419 zero-price codes also have paid sales.
- Proposals in the register are UNKNOWN or NEEDS_MANUAL_REVIEW.

### 8.2 PROPOSED

**P6.1** Zero price means zero revenue. No price is ever imputed.

**P6.2** Zero-price rows are retained and may represent physical movement, classified
separately (samples, promotions, replacements, write-offs, corrections, unknown).

**P6.3** Free-unit volume is reported separately from paid demand. It never enters revenue,
average selling price or value-based ABC.

**P6.4** Physical direction stays `UNKNOWN` until evidence exists. The 59 rows with
|quantity| ≥ 1,000 require individual review before any stock conclusion.

**P6.5** A zero-price row is never labelled a sale.

### 8.3 APPROVED

_None._

---

## 9. Policy 7 — Uncertainty and manual review

### 9.1 EXISTING

- 1,439 `UNKNOWN` + 1,581 `NEEDS_MANUAL_REVIEW` + 5 flagged financial adjustments =
  **3,025** `ManualReviewRequired = YES`.
- No queue, owner, SLA, resolution schema or audit history exists.

### 9.2 PROPOSED

**P7.1** `UNKNOWN` is permanent and legal. There is no "resolve all" operation.

**P7.2** A manual-review queue is created with: row reference, reason, dimension affected,
priority, owner, evidence required, state, resolution, resolver, timestamp, rule version.

**P7.3** Queue states: `OPEN`, `UNDER_REVIEW`, `RESOLVED`, `DEFERRED_EVIDENCE`,
`ACCEPTED_UNKNOWN`. `ACCEPTED_UNKNOWN` is a valid terminal state, recorded explicitly.

**P7.4** Every resolution requires evidence and an immutable audit entry. Bulk edits are
prohibited; each row carries its own justification.

**P7.5** Unresolved rows degrade the confidence of affected product metrics. They are not
dropped from the ledger and are not silently included in confident claims.

**P7.6** Priority order: rows that change a product's dead-stock status, then rows with
material value, then the remainder. The owner nominates the queue owner.

### 9.3 APPROVED

_None._

---

## 10. Policy 8 — Historical data preservation

### 10.1 EXISTING

- Protected hashes are recorded and unchanged.
- Git is unavailable; change evidence relies on hashes and timestamps.
- No versioned governed dataset exists beyond V1/V2.

### 10.2 PROPOSED

**P10.1** `data/raw` and `data/processed` V1/V2 are read-only. New work creates new versions;
it never edits an existing one.

**P10.2** Every derived dataset records: source SHA-256, transformation version, rule/policy
version, row counts, reconciliation results and approval reference.

**P10.3** No derived dataset may contain processing timestamps in its data rows (determinism).

**P10.4** A superseded dataset is retained, not overwritten. Deletion requires explicit owner
authorisation and a retention record.

**P10.5** Any future Git initialisation is an owner decision; it must not be done implicitly.

### 10.3 APPROVED

_None._

---

## 11. Policy 9 — Dead-stock measurement

### 11.1 EXISTING

- Dead-stock research defines 14 methodologies and a four-family score design (A historical,
  B current stock, C risk, D financial).
- Only historical sales-side metrics are computable: 3,898 baseline products, 460 with no sale
  in the final 180 days (historical line value £103,128.42), ABC 543/791/2,564, FSN
  2,830/632/436.
- No stock-on-hand, cost, receipts or current position exists.

### 11.2 PROPOSED

**P11.1** The five concepts remain separate: historical inactivity, current non-moving
inventory, actual dead stock, future risk, trapped capital. Only the first is available today.

**P11.2** No universal threshold. Thresholds are configuration, approved per business context.

**P11.3** A dead-stock label requires current stock evidence and an owner-approved definition.
Zero recent sales plus zero stock is "no activity", not dead stock.

**P11.4** Every assessment output includes: product, warehouse, assessment date, measurement
period, stock quantity, last sale, last movement, age (if available), demand measures, rule
version, evidence, missing fields, status and limitations.

**P11.5** If required inputs are missing, the result is `INSUFFICIENT_DATA` with the missing
field list — never a fabricated number.

**P11.6** Historical inactivity outputs must carry the literal label "no observed sale in the
period", not "dead stock".

### 11.3 APPROVED

_None._

---

## 12. Dead-stock definition proposal

This section proposes definitions; it does not set thresholds.

### 12.1 Definitions

| Term | Proposed definition | Required evidence | Available today? |
|---|---|---|---|
| **Non-moving inventory** | Stock on hand with no recorded movement (sale, transfer, adjustment) during the measurement window | Stock snapshot + movement history | No |
| **Slow-moving inventory** | Stock whose consumption rate over the window is below an approved rate threshold | Stock + demand history | No |
| **Excess inventory** | Stock above an approved coverage target (demand over lead time + safety) | Stock + demand + lead time | No |
| **Obsolete inventory** | Stock that can no longer be sold through normal channels (superseded, expired, discontinued) | Lifecycle/expiry data or owner declaration | No |
| **Dead stock** | On-hand stock meeting the approved non-moving/slow/obsolete rule with no reasonable recovery path | Stock + approved rule + recovery assessment | No |
| **At-risk inventory** | On-hand stock trending toward a dead-stock condition | Stock + demand trend + risk rule | No |
| **Historical inactivity** | No observed sale in a historical window (a sales-side fact only) | Sales history | **Yes, conditionally** |
| **Financially trapped inventory** | Value of dead stock at approved cost | Dead stock + acquisition cost | No |

### 12.2 Threshold dimensions

Thresholds should be configurable per: product category, business model, seasonality profile,
product lifecycle stage, procurement lead time, and operating cycle. A single 90/180-day rule
is a starting point, not a standard.

| Dimension | Proposed treatment | Why |
|---|---|---|
| Category | Per-category inactivity windows | Fashion vs hardware vs consumables differ |
| Seasonality | Compare against the same season, not the calendar year | A seasonal item is not dead in its off-season |
| Lifecycle | Shorter window near discontinuation | End-of-life stock becomes dead sooner |
| Lead time | Coverage target tied to lead time | Long-lead stock legitimately sits longer |
| Operating cycle | Align window to the business cycle | Cash-cycle reality differs by business |

### 12.3 What the owner must approve

1. The definition set in §12.1 (or modifications).
2. That no threshold is universal and thresholds are configuration.
3. That historical inactivity is reported as a separate, weaker concept.
4. That dead stock requires current stock evidence.
5. The rule-versioning and change-control process for thresholds.

---

## 13. Owner approval record

Allowed responses: `APPROVE`, `REJECT`, `MODIFY`, `DEFER`, `NEEDS_MORE_EVIDENCE`.

| Policy | Proposal | Owner response | Conditions | Date | Approver |
|---|---|---|---|---|---|
| P1 Transaction classification | Three dimensions; ordered rules | _pending_ | | | |
| P2 Product identity | Reversible canonical + alias table | _pending_ | | | |
| P3 Financial adjustments | Separate from product sales | _pending_ | | | |
| P4 Physical movement | Evidence required; default UNKNOWN | _pending_ | | | |
| P5 Duplicates | Flag, never delete | _pending_ | | | |
| P6 Zero price | Zero revenue; separate physical view | _pending_ | | | |
| P7 Uncertainty | Permanent UNKNOWN + queue + audit | _pending_ | | | |
| P8 Preservation | Immutable raw; versioned derived | _pending_ | | | |
| P9 Dead-stock measurement | Five concepts; configurable thresholds | _pending_ | | | |
| §12 Definitions | Definition set + threshold dimensions | _pending_ | | | |

---

## 14. Change control for approved policies

1. A proposal names the policy, the exact clause, the evidence, and the datasets affected.
2. The owner responds in writing; the response is recorded in the tracker, not only here.
3. An approved change bumps the policy version (V1 → V2) and the rule version.
4. All affected outputs are regenerated, reconciled and diffed; changed rows are listed by
   category, confidence and physical impact.
5. Superseded versions are retained.
6. No change is effective until steps 1–5 are complete.

---

## 15. Status

- Existing behaviour: unchanged.
- Proposed policies: 9 + a definition set, all `PENDING`.
- Approved policies: **none**.
- Implementation: **not started, and not authorised by this document**.

*End of Governance Policy Proposals V1.*
