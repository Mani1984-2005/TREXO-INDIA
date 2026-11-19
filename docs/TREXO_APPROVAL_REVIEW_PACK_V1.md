# TREXO-INDIA — APPROVAL REVIEW PACK V1

**Document:** Transaction Integrity, Inventory Intelligence and Dead-Stock Readiness
**Document ID:** `TREXO-APPROVAL-REVIEW-PACK-V1`
**Version:** V1 (first formal review issue)
**Status:** `READY_FOR_OWNER_REVIEW` — **no decision in this document is approved**
**Prepared by role:** Principal Data Engineer / Data Governance Auditor / Inventory Intelligence Architect / Technical Decision Analyst
**Repository:** `E:\TREXO-INDIA`
**Review date:** 2026-11-19
**Authority:** The project owner. This document is decision support, not a decision.

---

## 1. COVER AND DOCUMENT METADATA

### 1.1 Purpose

This pack converts the completed research and audit work into seven explicit, individually
reviewable governance decisions. For each decision it states the measured evidence, the
affected population, the financial and physical consequence, the existing treatment, the
viable alternatives, a recommendation, and the exact question the owner must answer.

Nothing in this document changes data, code, rules or reports. Nothing here is implemented.
No recommendation is presented as an approved rule.

### 1.2 Scope discipline

| Item | Position |
|---|---|
| New artefacts created | This document only (`docs/TREXO_APPROVAL_REVIEW_PACK_V1.md`) |
| Original dataset | Not modified |
| V1 / V2 processed datasets | Not modified |
| Existing scripts, reports, policy, register | Not modified |
| V3 dataset | Not created |
| Classification rules | Not implemented |
| Backend / frontend | Not built |
| Forecasting / ML | Not started |
| Transactions deleted or rewritten | None |

### 1.3 Evidence labelling used throughout

Every material statement is labelled with one of:

| Label | Meaning |
|---|---|
| **DIRECTLY VERIFIED** | Recomputed from `data/raw/Online Retail.xlsx` or read from a named artefact during this review |
| **DERIVED FROM SOURCE DATA** | Produced by an explicit, documented computation over source rows |
| **STRONGLY INFERRED** | Consistent with all available evidence but not provable from the dataset |
| **WEAKLY INFERRED** | A plausible reading supported by thin or ambiguous evidence |
| **UNRESOLVED** | Evidence is insufficient; the question stays open |

HIGH / MEDIUM / LOW appear only where they are literal values stored in the classification
register. They are never used here as a substitute for explaining evidence.

### 1.4 Reading guide

- Section 5 states the principles that constrain every recommendation.
- Sections 6–12 are the seven decisions, each using the mandatory 20-field structure.
- Sections 13–16 are cross-cutting: coverage, dependencies, dead-stock impact, evidence.
- Sections 17–19 are the owner-facing register, evidence requests and checklist.
- Section 20 is the closing recommendation summary — again, not an approval.

---

## 2. EXECUTIVE SUMMARY

### 2.1 Where the project stands

The transaction foundation is well measured but not yet governed. The Special Transaction
Audit V1 examined all **541,909** source rows, produced **93 open anomalies** (1 CRITICAL,
71 HIGH, 16 MEDIUM, 3 LOW, 2 INFORMATIONAL) and a **14,684-entry** classification register
that reconciles exactly to the source row count. No anomaly has been resolved. No rule has
been promoted. V3 does not exist.

### 2.2 The seven decisions in one page

| ID | Issue | Measured scale | Recommendation (not approved) |
|---|---|---|---|
| D01 | Bad-debt accounting rows on invoices A563185–A563187 | 3 rows, net **−£11,062.06**, £11,062.06 currently counted as V2 product sales | Separate financial-adjustment ledger; remove the group from product-sales analytics |
| D02 | Non-product and non-standard StockCodes inside V2 | **2,762** V2 rows, **£412,565.65** (4.02% of V2 value) across 24 raw code keys; 3,385 rows / 37 raw codes overall | Governed code registry with explicit physical-movement attribute; no blanket exclusion |
| D03 | Cancellation vs return vs write-off | **9,288** C-prefix negative rows; **1,336** non-C negative rows, all zero-price | Multi-dimensional classification (event / financial / physical); never infer stock increase from sign |
| D04 | Duplicate rows | **5,268** extra rows in **4,879** exact-duplicate groups, £21,740.98; 5,226 of them sit in V2 | Flag, never delete; deduplicate only under a documented business key |
| D05 | Zero-price transactions | **2,515** rows (1,179 positive, 1,336 negative), zero revenue, net −134,354 units | Independent financial and physical classifications; do not remove from inventory reasoning |
| D06 | Mixed-type / case-variant StockCodes | **487,036** int-typed + **54,873** str-typed values; 4,070 raw codes collapse to 3,958 case-folded keys | Reversible canonical ID; original always retained; no default merging |
| D07 | UNKNOWN / NEEDS_MANUAL_REVIEW | 1,439 + 1,581 = 3,020; manual-review flag = **3,025** | Evidence-based resolution workflow with immutable audit history; uncertainty never auto-collapses |

### 2.3 What this means for dead-stock intelligence

Historical, sales-side metrics (last sale date, frequency, velocity, ABC/XYZ/FSN) are
computable now, but their exact values are **conditional** on D01–D07. "Current non-moving
inventory", "actual dead stock", inventory ageing and financial exposure remain blocked by
missing inventory data regardless of these decisions. Historical sales inactivity must never
be reported as confirmed current dead stock.

### 2.4 The single most important finding

The three bad-debt rows do **not** net to zero. The positive row is +£11,062.06 and there are
**two** negative-price rows of −£11,062.06 each, giving a group net of **−£11,062.06**
(DIRECTLY VERIFIED). The accounting relationship is therefore not a simple sale-and-reversal
pair and cannot be asserted without the accounting ledger. This strengthens, rather than
weakens, the case for keeping the event intact and out of product analytics.

---

## 3. CURRENT PROJECT STATE

### 3.1 Artefacts found (Phase Zero inspection)

All paths relative to `E:\TREXO-INDIA`. Sizes and timestamps read from the file system on
2026-11-19.

| Artefact | Path | Size (bytes) | Last write |
|---|---|---|---|
| Original dataset | `data/raw/Online Retail.xlsx` | 23,715,344 | 2026-11-18 23:05:14 |
| Product movement V1 | `data/processed/product_movement_v1.csv` | 377,432 | 2026-11-18 23:16:31 |
| Product movement V2 | `data/processed/product_movement_v2.csv` | 558,626 | 2026-11-18 23:20:36 |
| Monthly sales V2 | `data/processed/product_monthly_sales_v2.csv` | 1,018,881 | 2026-11-18 23:20:36 |
| Special transaction audit script | `src/trexo/audit_special_transactions.py` | 157,666 | 2026-11-19 00:49:28 |
| Classification register | `reports/transaction_classification_register_v1.csv` | 11,358,970 | 2026-11-19 00:50:40 |
| Anomaly register | `reports/special_transaction_anomalies_v1.csv` | 47,708 | 2026-11-19 00:50:40 |
| Special stockcode analysis | `reports/special_stockcode_analysis_v1.csv` | 9,938 | 2026-11-19 00:50:40 |
| Zero-price description analysis | `reports/zero_price_description_analysis_v1.csv` | 62,648 | 2026-11-19 00:50:40 |
| Unusual invoice details | `reports/unusual_invoice_details_v1.csv` | 2,685,533 | 2026-11-19 00:50:40 |
| Invoice prefix analysis | `reports/invoice_prefix_analysis_v1.csv` | 625 | 2026-11-19 00:50:40 |
| Audit report | `reports/special_transaction_audit_v1.md` | 46,544 | 2026-11-19 00:50:41 |
| Classification policy | `docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md` | 20,368 | 2026-11-19 00:56:35 |
| Dead-stock research | `docs/DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md` | 52,537 | 2026-11-19 01:04:23 |
| Data requirements | `docs/DEAD_STOCK_DATA_REQUIREMENTS_V1.md` | 13,555 | 2026-11-19 01:07:40 |
| Intelligence architecture | `docs/TREXO_INTELLIGENCE_ARCHITECTURE_V1.md` | 15,325 | 2026-11-19 01:06:18 |
| Application architecture | `docs/TREXO_APPLICATION_ARCHITECTURE_PROPOSAL_V1.md` | 15,056 | 2026-11-19 01:07:13 |
| Automated tests | `tests/test_audit_special_transactions.py` | 24,960 | 2026-11-19 00:53:48 |

Additional supporting files: `README.md` (546 B), `docs/DATA_SOURCE_REGISTER.md` (593 B),
`requirements-lock.txt` (1,157 B), plus earlier profiling/reconciliation modules under
`src/trexo/`.

### 3.2 Runtime and tooling

- Python 3.11.9, pandas 3.1.1, numpy 2.4.6, openpyxl available in `.venv` (DIRECTLY VERIFIED).
- `pytest` is not installed; the existing suite runs on the standard-library `unittest`
  runner. This review did not add dependencies.

### 3.3 Version-control status

`git rev-parse --is-inside-work-tree` → `fatal: not a git repository`, exit code **128**
(DIRECTLY VERIFIED). **Git-based change verification is unavailable.** Change evidence in
this pack therefore relies on SHA-256 hashes before and after, plus file-system timestamps.
Git was not initialised.

### 3.4 What is complete vs open

| Capability | State |
|---|---|
| Source profiling and reconciliation | COMPLETED (audit) |
| V1 / V2 product movement | COMPLETED, protected |
| Transaction classification register | COMPLETED, proposed, not approved |
| Anomaly register | COMPLETED, 93/93 `OPEN` |
| Dead-stock research (methods, formulas, limits) | COMPLETED, research only |
| Governance decisions D01–D07 | **PENDING OWNER** |
| V3 dataset | NOT CREATED (correctly blocked) |
| Current-stock / dead-stock detection | BLOCKED_BY_EXTERNAL_DATA |

---

## 4. REPOSITORY AND PROTECTED-FILE VERIFICATION

### 4.1 Protected-file hashes — before writing this pack

Computed with `Get-FileHash -Algorithm SHA256`:

| File | SHA-256 (before) |
|---|---|
| `data/raw/Online Retail.xlsx` | `43465A06F2CCF7C8B5BD2892BC7DEFB52F97487934FE93B16AE4C3936424676D` |
| `data/processed/product_movement_v1.csv` | `43EAF924A58D538E843C32B5CE5A975AA611D10BFDBC9CB064F1E899ACF7C3CD` |
| `data/processed/product_movement_v2.csv` | `11B5378A63EBD6A62EDEC83D8EBA6BDE94C28BEE78F8D1CA526CE810215678DB` |
| `data/processed/product_monthly_sales_v2.csv` | `C9B6ABD8E9CB5E967A755D9BC26BA40FBCB4D4136FFB09EE4C261E93EE5676CC` |

These match the hashes recorded at the end of the previous phase (DIRECTLY VERIFIED).

### 4.2 Immutability method

Because Git is unavailable, this review used three independent controls:

1. **Hash guard** — the four protected datasets are hashed before and after the review.
2. **Write confinement** — the only file written inside the repository is this document.
   Diagnostic scripts were written to `C:\Users\naman\AppData\Local\Temp\opencode\`.
3. **Timestamp inspection** — artefact modification times in §3.1 predate this review and are
   re-checked after writing.

### 4.3 Reproduction of audit figures

Rather than trusting the previous summary, the review recomputed, from the raw workbook:
row count, invoice count, StockCode typing, the three A-invoices, per-code aggregates,
negative-quantity partitions, duplicate keys, zero-price rows, normalization collisions,
register scope totals and coverage identity. Results are reported inline and summarised in
§13 and §16. Where a figure could not be reproduced, it is marked and explained.

---

## 5. DECISION-MAKING PRINCIPLES

These principles bind the recommendations and should bind future implementation.

1. **Traceability before tidiness.** Every row keeps its `SourceRow` reference. No cleaning
   step may destroy the ability to return to the original workbook.
2. **Financial impact and physical movement are separate dimensions.** A row can be a
   financial adjustment with no stock effect, a stock movement with no revenue, both, or
   neither. One field must never carry both meanings.
3. **Sign is not semantics.** A negative quantity is not automatically a return; a positive
   quantity is not automatically a sale. Evidence, description, invoice relationship and
   price behaviour must agree before a business event is asserted.
4. **Zero price is not zero movement.** Free goods can consume real inventory.
5. **Uncertainty is a result, not a failure.** `UNKNOWN` must survive into downstream
   reporting; it may not be silently forced into the nearest category.
6. **Historical inactivity is not current dead stock.** Without a stock snapshot, no claim
   about present inventory or trapped capital is admissible.
7. **No silent deletion.** Duplicates, cancellations and adjustments are preserved; any
   future exclusion is a governed *analytical view*, not a source-data edit.
8. **Reversibility.** Normalization and identity merges must be undoable from the original
   identifier.
9. **Owner authority.** A technical recommendation is an input to a business decision, never
   a substitute for one.
10. **Reproducibility.** Any rule that is eventually approved must be deterministic, tested
    and versioned; the current outputs contain no run timestamps for that reason.

---

## 6. D01 — BAD-DEBT TRANSACTION (INVOICES A563185 / A563186 / A563187)

### 20-field decision structure

**1. Decision ID and title**
D01 — Treatment of the bad-debt accounting event recorded on invoices A563185, A563186 and
A563187 (StockCode `B`, description "Adjust bad debt"). Anomaly `ANOM-0001` (CRITICAL).

**2. Exact problem statement**
One positive-price row on invoice A563185 satisfies the V2 sale definition and is counted as
£11,062.06 of product revenue. Two associated rows on A563186 and A563187 carry negative unit
prices and are excluded from V2. The dataset cannot establish whether the three rows form one
accounting event, why there are two credits, or whether any physical goods moved. The owner
must decide how this event is treated in product movement and revenue analytics.

**3. Why the decision matters to TREXO**
A bad-debt write-off is a financial event, not a sale. Counting it as product revenue
distorts revenue totals, average selling price, product rankings and any value-based ABC
classification. Because it is a single large line (CRITICAL severity), it can move a product
or a reporting period more than thousands of ordinary rows. It is also the clearest test of
whether TREXO's foundation can keep financial adjustments out of physical-product analytics.

**4. Relevant source evidence**
All DIRECTLY VERIFIED from the workbook and reproduced this review:

| SourceRow | Invoice | StockCode | Description | Qty | UnitPrice | Line value | InvoiceDate | CustomerID | Country |
|---|---|---|---|---|---|---|---|---|---|
| 299984 | A563185 | B | Adjust bad debt | 1 | 11,062.06 | +11,062.06 | 2011-08-12 14:50 | missing | United Kingdom |
| 299985 | A563186 | B | Adjust bad debt | 1 | −11,062.06 | −11,062.06 | 2011-08-12 14:51 | missing | United Kingdom |
| 299986 | A563187 | B | Adjust bad debt | 1 | −11,062.06 | −11,062.06 | 2011-08-12 14:52 | missing | United Kingdom |

Invoice prefix evidence: the only three `A`-prefixed invoices in the dataset are these three
(`invoice_prefix_analysis_v1.csv`; the first-character distribution is 532,618 numeric,
9,288 `C`, 3 `A`). The three timestamps are one minute apart, which is consistent with a
single manual accounting sequence (STRONGLY INFERRED).

**5. Exact affected record counts**
3 source rows; 3 invoices; 1 StockCode (`B`); 0 rows with a CustomerID. The entire StockCode
`B` population in the dataset is these 3 rows (DIRECTLY VERIFIED).

**6. Affected invoices and products**
Invoices A563185, A563186, A563187. "Product" is nominal only: `B` has no product
description, no customer, no price consistency and no physical-movement evidence. It is an
administrative code, not a merchandise identifier (DIRECTLY VERIFIED for attributes;
STRONGLY INFERRED for the interpretation).

**7. Financial impact**
- Positive line counted in V2: **£11,062.06** (DIRECTLY VERIFIED in
  `product_movement_v2.csv`: StockCode `B`, TotalSalesValue 11,062.06).
- Group net across all three rows: **−£11,062.06** (DIRECTLY VERIFIED). The group is
  *not* a zero-sum reversal pair.
- Removal of the positive line from product-sales analytics would reduce reported product
  revenue by £11,062.06. Removal of all three from a *financial* ledger would be wrong: the
  event has a real net accounting effect that must remain visible somewhere.
- Share of V2 product value: approximately 0.11% of £10.25m (DERIVED FROM SOURCE DATA).

**8. Physical inventory impact**
No evidence of physical movement. Quantity is +1 on all three rows; there is no customer, no
shipping reference, no product description and no stock location. The description states an
accounting adjustment. Classification: `NO_PHYSICAL_STOCK_MOVEMENT` for the group
(STRONGLY INFERRED; the dataset cannot prove the absence of goods, but provides no positive
evidence of them).

**9. Current V2 treatment**
V2's sale rule is: invoice not starting with `C` AND quantity > 0 AND unit price > 0.
- A563185 qualifies → included as a product sale of £11,062.06, quantity 1, invoice count 1.
- A563186 and A563187 fail the price > 0 test → excluded.
This asymmetry is the defect: one leg of an accounting entry is treated as merchandise and
the offsetting legs are not.

**10. Existing classification register treatment**
`transaction_classification_register_v1.csv` holds one ROW entry per source row (REG IDs for
SourceRow 299984–299986). The positive row is proposed as `FINANCIAL_ADJUSTMENT` with
`NO_PHYSICAL_STOCK_MOVEMENT`; it is flagged `ManualReviewRequired=YES` (one of the 5
financial-adjustment rows so flagged). Anomaly `ANOM-0001` remains `OPEN`. The register
proposes; it does not decide.

**11. Available decision alternatives**
- **A. Retain existing V2 treatment.** Leave the positive row in product movement.
- **B. Exclude the complete accounting group from future product movement.** Remove all three
  from any product-sales dataset.
- **C. Preserve the records in a separate financial adjustment ledger.** Keep them out of
  product movement but visible as a financial event with its net value.
- **D. Keep all records in raw transactions but prevent their inclusion in product sales
  analytics.** Raw layer unchanged; analytical views exclude the event; no new ledger
  artefact is required before approval.

**12. Advantages of each alternative**
- A: zero effort; no change to historical outputs; preserves the ability to reconcile to V2.
- B: simplest conceptual rule; guarantees the group cannot leak into product totals.
- C: cleanest separation of concerns; preserves the accounting event and its net effect for
  finance-facing reporting; directly supports audit.
- D: achieves the analytical objective without creating a new governed store before the owner
  has approved a financial-adjustment concept; fully reversible.

**13. Disadvantages of each alternative**
- A: knowingly reports a write-off as product revenue; contaminates revenue, ASP and
  value-based rankings; fails the "financial ≠ physical" principle.
- B: hides a real financial event; the net −£11,062.06 becomes invisible; loses the audit
  trail unless the ledger is built anyway.
- C: requires a new governed entity and owner approval of its schema; more work than the
  immediate need; risks becoming a parallel source of truth if not linked to `SourceRow`.
- D: product analytics are corrected but finance still has no dedicated view until C is
  approved; relies on view definitions being applied consistently everywhere.

**14. Downstream consequences**
Any revenue total, average price, revenue-per-product, ABC-by-value or "top products" ranking
computed from V2 currently includes £11,062.06 of non-merchandise value. If V3 is built
without a decision, the same contamination is inherited and becomes harder to unwind. If the
group is excluded, historical V2 figures and future V3 figures will differ by exactly
£11,062.06 and that difference must be documented, not silently absorbed.

**15. Interaction with dead-stock intelligence**
The affected "product" (`B`) has no physical existence, so it should never enter a product
population, recency ranking or FSN/ABC analysis. Left in place it creates a phantom product
with a single sale and a large value, which can distort product counts and value-based ABC
thresholds. It does not affect unit-based velocity materially (quantity 1), but it can shift
value concentration. Correct treatment removes a false positive from the product universe.

**16. Recommended approach**
**Recommend D as the immediate treatment, with C as the target architecture.**
Specifically: retain all three rows in the raw and staging layers; define the group as a
financial adjustment with `NO_PHYSICAL_STOCK_MOVEMENT`; exclude the whole group from product
sales and product movement views; preserve the net −£11,062.06 in a financial-adjustment view
when the owner approves that entity. Do **not** implement now. B alone is rejected because it
hides the financial event; A is rejected because it misstates product revenue.

**17. Risks of the recommendation**
- Two views of "revenue" (product vs financial) can drift if not documented; the pack
  therefore fixes the reconciliation identity: `product revenue + financial adjustments =
  total accounting revenue`.
- Excluding an event that later proves to be a genuine sale would understate revenue by
  £11,062.06; the accounting ledger is the evidence that resolves this.
- Scope creep: the adjustment is one row, but the principle applies to all `A`-prefix and
  negative-price events; the rule must be general, not a one-off patch.

**18. Evidence still missing**
The accounting ledger, journal reference, or credit-note documentation that explains why
there are two −£11,062.06 lines against one +£11,062.06 line, and whether the net
−£11,062.06 is the intended posting. Also missing: any statement from the business that
`B` is an administrative code. These are external to the dataset.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer the treatment of invoice group A563185–A563187. Specifically:
(a) confirm that `B` is an administrative/financial code and not a product; (b) choose
whether the group is excluded from product sales analytics (recommended) or retained;
(c) confirm that the net financial effect must remain visible in a separate financial view."

**20. Proposed approval status**
`PENDING` — owner decision required. Current operational status: V2 unchanged; anomaly
`ANOM-0001` remains `OPEN`; no rule implemented.

---

## 7. D02 — NON-PRODUCT STOCKCODES IN V2

### 20-field decision structure

**1. Decision ID and title**
D02 — Governance of non-product, service and non-standard StockCodes in product movement.

**2. Exact problem statement**
V2 product movement contains 2,762 rows carrying **£412,565.65** on 24 raw StockCode keys that
are not ordinary five-digit merchandise codes. Some are shipping, some are fees, some are
financial adjustments, some are promotional instruments, and at least one (`15056BL`) is a
genuine physical product whose code simply fails the standard pattern. Treating them all as
"non-product" would delete real merchandise; leaving them all in place contaminates product
counts, revenue and dead-stock rankings. A governed rule is required.

**3. Why the decision matters to TREXO**
Product counts, revenue per product, average price, ABC value thresholds and FSN/ABC
populations all depend on what counts as a product. A blanket exclusion or a blanket
inclusion both produce confidently wrong answers. TREXO needs an explicit, auditable product
identity boundary so that "3,898 products" means something reproducible.

**4. Relevant source evidence**
DIRECTLY VERIFIED this review. Per-code table (V2 value = sum over rows satisfying the V2
sale definition; total value = all rows):

| Code / family | Records | Invoices | Total qty | Total value (£) | Zero-price rows | Negative-price rows | In V2? | V2 value (£) | Evidence-based class |
|---|---|---|---|---|---|---|---|---|---|
| POST | 1,256 | 1,254 | 6,353 | 66,230.64 | 4 | 0 | YES | 78,101.88 | Shipping/service |
| DOT | 710 | 710 | 1,707 | 206,245.48 | 3 | 0 | YES | 206,248.77 | Shipping/service |
| M + m | 572 | 518 | 3,165 | −68,671.64 | 6 | 0 | YES | 78,112.82 | Administrative ("Manual") |
| AMAZONFEE | 34 | 34 | −30 | −221,520.50 | 0 | 0 | YES | 13,761.09 | Financial adjustment |
| BANK CHARGES | 37 | 36 | −13 | −7,175.64 | 0 | 0 | YES | 165.001 | Financial adjustment |
| CRUK | 16 | 16 | −16 | −7,933.43 | 0 | 0 | **NO** | 0 | Financial/charity adjustment |
| C2 | 144 | 144 | 290 | 6,986.00 | 1 | 0 | YES | 7,051.00 | Shipping/service ("CARRIAGE") |
| S | 63 | 19 | −59 | −3,049.39 | 0 | 0 | YES | 63.05 | Promotional/samples |
| PADS | 4 | 4 | 4 | 0.003 | 1 | 0 | YES | 0.003 | Promotional goods |
| B | 3 | 3 | 3 | −11,062.06 | 0 | 2 | YES | 11,062.06 | Financial adjustment (D01) |
| D | 77 | 65 | −1,194 | −5,696.22 | 0 | 0 | **NO** | 0 | Financial ("Discount") |
| 15056BL (both cases) | 388 | 388 | 2,801 | 16,263.22 | 0 | 0 | YES | **16,915.72** | **Physical product** |
| GIFT_* (5 codes) | 34 | 30 | 103 | **685.81** | 3 | 0 | YES | 685.81 | Promotional instrument (voucher) |
| DCGS* (16 codes) | 45 | 39 | 45 | **398.45** | 12 | 0 | partial | 398.45 | Mixed / unresolved |
| 79323GR | 1 | 1 | −1,158 | 0 | 1 | 0 | NO | 0 | Stock write-off ("Unsaleable, destroyed.") |
| 79323LP | 1 | 1 | −2,618 | 0 | 1 | 0 | NO | 0 | Stock write-off ("Unsaleable, destroyed.") |

Aggregate checks (DIRECTLY VERIFIED):
- Sum of V2 values in `special_stockcode_analysis_v1.csv` = **£412,565.65**; the same figure is
  obtained by summing V2-definition rows whose code fails `\d{5}[A-Za-z]?`.
- Those rows number **2,762**, on **24** raw codes (**22** after case folding).
- `15056BL` family: 383 V2-eligible rows, £16,915.72; the family's total across all rows is
  £16,263.22 because five negative-quantity rows are excluded from V2. The assignment's
  £16,915.72 is therefore **verified as the V2 value**, not the raw total.
- `GIFT_*` £685.81 and `DCGS*` £398.45 are **verified exactly**.
- `AMAZON` does not exist in the dataset; `AMAZONFEE` is the real code (reported, not
  substituted). This is recorded as an INFORMATIONAL anomaly.

**5. Exact affected record counts**
- In V2: 2,762 rows, 24 raw code keys, £412,565.65.
- In the full dataset: 3,385 rows on 37 raw codes fail the standard pattern (plus case and
  length variants); 22 distinct uppercase families.
- V2 contains 3,922 product rows in total, so non-standard codes are 2,762/3,922 ≈ 70% of
  V2 *rows* while contributing 4.02% of V2 value — a stark row/value asymmetry worth
  remembering when choosing metrics.

**6. Affected invoices and products**
2,762 V2 rows across many invoices; the largest invoice presence is POST (1,254) and DOT
(710). `15056BL` alone has 321 V2 invoices and 388 raw invoices. No single invoice group
dominates financially except the AMAZONFEE and B adjustments.

**7. Financial impact**
- Removing all non-standard codes from V2 would remove **£412,565.65** (4.02% of
  £10,254,118.89 V2 product value).
- Removing only the evidence-supported financial/service codes (POST, DOT, M/m, AMAZONFEE,
  BANK CHARGES, C2, B, D, CRUK) would remove approximately **£400,600** of value and about
  2,300 rows; `15056BL` (£16,915.72) and GIFT/DCGS would remain.
- Blanket exclusion would also delete a genuine product worth £16,915.72 — a real merchandise
  error, not a cleaning improvement.

**8. Physical inventory impact**
Heterogeneous. POST/DOT/C2 are services with no stock. M/m "Manual" has no product identity.
B/D/AMAZONFEE/BANK CHARGES/CRUK are financial. GIFT vouchers are financial instruments, not
goods. PADS and S may correspond to physical promotional stock but the dataset does not prove
it. `15056BL` is physical merchandise (description "EDWARDIAN PARASOL BLACK", 2,844 units
sold). `79323GR/LP` are stock write-offs of physical goods, recorded at zero price. `DCGS*`
descriptions include party bags, collars and ashtrays — plausibly physical, but the code
family is inconsistent and unresolved.

**9. Current V2 treatment**
All codes that pass the sale definition are aggregated as products. `CRUK` and `D` are absent
from V2 only because their rows are negative quantity; they are not excluded by policy.
`15056BL` appears as two separate V2 rows (`15056BL` and `15056bl`), splitting one product's
history across two identities.

**10. Existing classification register treatment**
ROW-level entries exist for every non-standard-code row (the register's row-level predicate
includes `~IsStandardStockCode`). Proposed categories vary: SHIPPING_CHARGE (POST, DOT, C2),
FINANCIAL_ADJUSTMENT (B, D, AMAZONFEE, BANK CHARGES, CRUK), SERVICE_CHARGE,
PHYSICAL_STOCK_MOVEMENT (`15056BL`), NEEDS_MANUAL_REVIEW and UNKNOWN for ambiguous families.
`ANOM-0004`–`ANOM-0007` and `ANOM-0031`-type findings remain `OPEN`.

**11. Available decision alternatives**
- **A. Exclude all non-standard codes.**
- **B. Exclude only evidence-supported financial and service codes.**
- **C. Maintain a governed product-code registry with explicit classification and physical
  movement attributes.**
- **D. Preserve all codes in the transaction ledger while separating product sales, service
  charges and financial adjustments in analytical views.**

**12. Advantages of each alternative**
- A: trivial to state; guarantees no service line can enter product metrics.
- B: targeted; protects genuine products such as `15056BL`; immediately improves revenue
  accuracy.
- C: durable; creates one authoritative place to record what each code is, with evidence and
  an owner; supports new codes as they appear.
- D: no destructive exclusion; reporting can present product, service and financial views
  separately while preserving total reconciliation.

**13. Disadvantages of each alternative**
- A: deletes a real product and several ambiguous physical families; fails the "do not assume
  every non-standard code is non-product" instruction.
- B: still a hard-coded list that will drift; gives no home for future codes; does not solve
  `15056BL`/`15056bl` identity splitting.
- C: requires governance effort, a schema and owner-approved entries; a registry without an
  enforcement mechanism can become stale.
- D: without C, the separation rules live only in query code and can be applied
  inconsistently; "product sales" may mean different things in different reports.

**14. Downstream consequences**
Product counts: V2 contains 3,922 code rows, of which **24 are non-standard code keys**
(including `15056BL` and `15056bl` as separate keys). A blanket exclusion would therefore
produce 3,898 code rows — but it would delete a genuine product. The correct product count is
3,898 **plus** the retained `15056BL` family (i.e. 3,899 distinct products after identity
merging), not 3,898 achieved by excluding it. Note that the research baseline's 3,898 already
reflects the blanket-exclusion assumption and therefore omits `15056BL`'s £16,915.72; this is
an inconsistency between artefacts that the owner should be aware of, not a data error.
Revenue: product revenue would move from £10.25m toward £9.84m under the recommended
separation. Dead-stock: recency and FSN rankings for POST/DOT would disappear (good), while
`15056BL` must stay (critical). ABC-by-value would otherwise be distorted by AMAZONFEE and B.

**15. Interaction with dead-stock intelligence**
Non-product codes must not occupy dead-stock population slots: POST can never be "dead
stock". Conversely, `15056BL` must be preserved or TREXO loses a fast-moving product. GIFT
vouchers have zero physical stock and must not create recovery recommendations. DCGS
ambiguity can create false positives until resolved.

**16. Recommended approach**
**Recommend C + D together, implemented as one governed mechanism.** Build (after approval) a
product-code registry that records, per code: canonical code, original variants, class
(physical product / shipping / service / financial adjustment / promotional / administrative /
unknown), physical-movement attribute, evidence reference and owner approval. Analytical
views then separate product sales, service charges and financial adjustments while the
transaction ledger keeps every row. For the immediate question, use option B's evidence-based
list as the *initial registry content*, explicitly retaining `15056BL` as physical product and
marking DCGS/S/PADS as `UNKNOWN` pending evidence.

**17. Risks of the recommendation**
- Registry maintenance becomes a bottleneck if every new code needs manual approval; mitigate
  with a default `UNKNOWN` class that never silently enters product metrics.
- Classifying `M` as administrative could be wrong if "Manual" denotes a physical manual
  product; the evidence (no consistent price, 3,165 units, mixed signs) is ambiguous.
- Case-folding `15056BL` merges two V2 rows; that is desirable but must be reversible (D06).
- Over-exclusion could hide legitimate service revenue from finance reporting; hence the
  separate service view.

**18. Evidence still missing**
Business confirmation for: `M`/`m` meaning; whether `S` and `PADS` are physical promotional
stock; what `DCGS*` codes represent; whether `CRUK` is a charity commission adjustment. Also
missing: a supplier/product master that would settle physical identity definitively.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) the principle that product movement contains only
physical merchandise; (b) the initial classification of each code family in the table above;
(c) whether a governed product-code registry (recommended) becomes the single source of
truth; (d) explicit confirmation that `15056BL` is a physical product and must not be
excluded."

**20. Proposed approval status**
`PENDING` — owner decision required. No code has been excluded from V2.

---

## 8. D03 — CANCELLATION VERSUS CUSTOMER RETURN

### 20-field decision structure

**1. Decision ID and title**
D03 — Separating cancellation, customer return, refund, credit adjustment, inventory reversal,
damaged goods and administrative correction.

**2. Exact problem statement**
The dataset records negative quantities in two very different populations: 9,288 rows on
`C`-prefixed invoices and 1,336 rows on ordinary invoices. The first group is conventionally
read as cancellation; the second is not a cancellation but has no explicit event type. Neither
group proves physical stock returned. The owner must decide the classification architecture
for negative movements.

**3. Why the decision matters to TREXO**
Net quantity, return rate, demand velocity and stock-flow reasoning all depend on this. If
every negative quantity is treated as a return, TREXO will overstate returns and understate
net demand. If every cancellation is treated as a stock increase, TREXO will claim inventory
it cannot prove. The distinction also determines whether a cancelled sale should be removed
from demand history or netted against it.

**4. Relevant source evidence**
DIRECTLY VERIFIED:
- Total negative-quantity rows: **10,624**.
- `C`-prefix negative rows: **9,288** (87.4%), value **−£896,812.49**.
- Non-`C` negative rows: **1,336** (12.6%), value **£0.00** — every one has UnitPrice = 0.
- Non-`C` negative rows: 1,336 distinct invoices, 1,082 distinct codes, 1,719 negative rows
  overall have no CustomerID.
- Invoice first-character distribution: `5` 532,618; `C` 9,288; `A` 3.
- Of 9,288 cancellations, **8,882** have a same-customer, same-code positive sale on or before
  the cancellation date (95.6%); 406 do not (DERIVED FROM SOURCE DATA).
- The 1,336 non-`C` negative rows carry descriptions such as "damages", "damaged", "found",
  "check", "thrown away", "Unsaleable, destroyed." — i.e. stock-adjustment language, not
  refund language (DIRECTLY VERIFIED from descriptions; interpretation STRONGLY INFERRED).

**5. Exact affected record counts**
10,624 negative-quantity rows; 9,288 cancellation; 1,336 non-cancellation. 1,719 negative rows
lack a CustomerID. 108,712 rows lack a CustomerID overall.

**6. Affected invoices and products**
All 9,288 `C` invoices; 1,336 ordinary invoices carrying negative rows (each such invoice has
exactly one negative row by construction of the count). 1,082 distinct codes in the non-`C`
negative population, including `79323GR` (−1,158) and `79323LP` (−2,618) described as
"Unsaleable, destroyed."

**7. Financial impact**
Cancellation value −£896,812.49. Non-cancellation negative rows have **zero** financial value
because their price is zero; they are pure quantity adjustments. Any "return rate" computed as
negative rows / positive rows (10,624 / 531,285 ≈ 2.0%) mixes two economically different
events and should not be used as a financial returns metric.

**8. Physical inventory impact**
For cancellations: a physical return is plausible but unproven — the dataset records a
reversal of a sale, not a warehouse receipt. For the 1,336 zero-price negative rows: the
descriptions ("damages", "destroyed", "found") suggest stock write-offs or corrections, which
would be physical *decreases* (or corrections of prior errors), yet the dataset does not
record stock direction. Physical impact must remain `UNKNOWN` (UNRESOLVED) for both groups
unless a stock movement record exists.

**9. Current V2 treatment**
`C`-prefix rows are excluded from V2 by the invoice-prefix rule. The 1,336 non-`C` negative
rows are excluded by the quantity > 0 rule. So neither group enters product sales, but for
different reasons, and neither is separately represented in V2. Demand calculations that use
only V2 therefore see gross positive sales, not net demand.

**10. Existing classification register treatment**
All 9,288 cancellation rows are ROW entries with `CANCELLATION`, `REVENUE_REVERSAL_NEGATIVE`,
`UNKNOWN_PHYSICAL_IMPACT` (8,704 of them HIGH confidence; 305 NEEDS_MANUAL_REVIEW; the
remainder distributed). The 1,336 non-`C` negative rows are `NEEDS_MANUAL_REVIEW` (298) or
`UNKNOWN` (855) plus other proposals, all with `UNKNOWN_PHYSICAL_IMPACT`. Anomalies
`ANOM-0019` (cancellation without original order linkage), `ANOM-0020` (negative quantity
without description) and `ANOM-0021` (negative quantity without customer) remain `OPEN`.

**11. Available decision alternatives**
- **A. Treat every negative cancellation record as a cancellation.**
- **B. Treat every negative quantity as a customer return.**
- **C. Maintain separate cancellation, return, financial-credit and unknown classifications.**
- **D. Use a multi-dimensional classification separating business event, financial impact and
  physical inventory impact.**

**12. Advantages of each alternative**
- A: simple, matches the invoice-prefix convention, and is right for the majority.
- B: one rule, no ambiguity, easy to explain.
- C: distinguishes economically different events and prevents false return rates.
- D: preserves all three questions independently; supports evidence upgrades without
  reclassifying unrelated dimensions; aligns with the existing register schema.

**13. Disadvantages of each alternative**
- A: ignores the 1,336 non-`C` rows and still cannot say whether stock returned.
- B: demonstrably wrong for 1,336 zero-price write-offs and for cancellations with no prior
  sale; conflates revenue reversal with physical movement.
- C: still a single-label model; a cancellation can be simultaneously a financial reversal and
  an unknown physical event, which one label cannot express.
- D: more fields and more governance; requires the owner to accept "unknown" as a durable
  state.

**14. Downstream consequences**
A single-label model forces a choice between financial and physical truth in every downstream
join. Multi-dimensional classification lets net revenue use the financial dimension and stock
analysis use the physical dimension, without either corrupting the other. Report definitions
must state which dimension they use; otherwise "returns" will mean different things in
different dashboards.

**15. Interaction with dead-stock intelligence**
If cancellations are netted into demand, a product with heavy cancellation looks less popular
than it is. If they are ignored, demand is overstated. The defensible approach is to report
gross sales, cancellations and net sales separately, and to keep physical return quantities
out of stock calculations until evidence exists. The 1,336 zero-price adjustments must not
be read as demand at all.

**16. Recommended approach**
**Recommend D, implemented through C's category vocabulary.** Concretely: three independent
fields — business event (sale / cancellation / return / write-off / correction / unknown),
financial impact (positive revenue / reversal / zero / non-product), physical impact
(decrease / increase / none / unknown). Quantity sign is one input, never the classifier.
Preserve the 95.6% sale-match statistic as evidence, not as proof of physical return.

**17. Risks of the recommendation**
- Three fields increase modelling and reporting complexity; without discipline, consumers will
  pick the wrong one.
- The 406 unmatched cancellations may include genuine data errors; forcing them into
  "cancellation" would hide that.
- If the business later confirms that all `C` invoices represent physical returns, the
  physical dimension can be upgraded — but only with evidence, and the audit history must show
  who changed it and why.

**18. Evidence still missing**
Warehouse returns records, credit notes, and any linkage between `C` invoices and original
orders. The dataset has no order ID, so the 8,882 "matches" are customer+code+date inferences,
not proven links. Descriptions for 1,454 zero-price rows are missing, including many of the
1,336 negative adjustments.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) the three-dimension classification model (event /
financial / physical); (b) the rule that quantity sign alone never determines a return;
(c) whether cancellations may ever be counted as physical stock increases without a stock
record (recommended: no); (d) how net demand should be reported (gross + cancellations + net,
recommended)."

**20. Proposed approval status**
`PENDING` — owner decision required. No cancellation rule has been changed.

---

## 9. D04 — DUPLICATE RECORDS

### 20-field decision structure

**1. Decision ID and title**
D04 — Treatment of 5,268 duplicate transaction rows.

**2. Exact problem statement**
Using all eight source columns as the key (InvoiceNo, StockCode, Description, Quantity,
InvoiceDate, UnitPrice, CustomerID, Country), **5,268 rows** are extra copies within **4,879**
duplicate groups. The dataset cannot distinguish a data-entry duplication from a legitimate
repeated line (same product, same invoice, same instant, same price). Deleting them would
change history; ignoring them may double-count demand.

**3. Why the decision matters to TREXO**
Duplicates inflate quantity, invoice-line counts and velocity. Because 5,226 of the 5,268 extra
rows pass the V2 sale definition, V2 currently contains them. Any historical demand measure —
sales frequency, units per invoice, FSN consumption rate — inherits the inflation. Conversely,
removing genuine repeat lines would understate demand. The decision defines how TREXO treats
identity in transaction history.

**4. Relevant source evidence**
DIRECTLY VERIFIED this review:
- Detection key: the eight source columns above (identical to the audit's key).
- Extra rows (keep-first): **5,268**; rows participating in any duplicate group: 10,147.
- Duplicate groups: **4,879**.
- Group sizes: 2 rows ×4,588; 3 ×238; 4 ×39; 5 ×5; 6 ×6; 8 ×1; 12 ×1; 20 ×1.
- Affected invoices: **1,933**; affected products: **1,706**; distinct dates: 1,914.
- Extra-row financial value: **£21,740.98**; extra quantity: 13,948 units.
- Of the 5,268 extra rows: 5,226 are P07 (paid, positive) worth **£24,573.74** and 15,956
  units; 37 are cancellation rows; 5 are zero-price.
- Excluding Description from the key raises the count only from 5,268 to 5,270, so
  description differences are not driving the finding.
- Invoice-line multiplicity (same invoice + same StockCode) affects 9,694 invoice/code pairs
  and 20,378 rows — a much broader phenomenon that includes legitimate multi-line orders.

**5. Exact affected record counts**
5,268 extra rows; 4,879 groups; 1,933 invoices; 1,706 products; 5,226 extra rows inside V2.

**6. Affected invoices and products**
1,933 invoices and 1,706 products. Because duplicates are exact on timestamp, they are more
consistent with a repeated load or a duplicated line entry than with two genuine purchases at
different times (STRONGLY INFERRED, not proven).

**7. Financial impact**
£21,740.98 of line value across extra rows; £24,573.74 within the V2 sale subset (the V2 subset
is larger because it excludes the 37 negative rows). Removing duplicates would reduce V2
revenue by that amount and reduce units by 15,956 (0.9% of positive quantity).

**8. Physical inventory impact**
Unknown. If the duplicate is a data artefact, no extra stock moved. If it represents two
physical units despatched but only one line recorded, the duplicate row is the only evidence
of the second movement. The dataset cannot decide; physical impact stays `UNKNOWN`.

**9. Current V2 treatment**
Duplicates are included. V2 aggregates all qualifying rows, so the extra copies contribute to
TotalQuantitySold, InvoiceCount and TotalSalesValue. A deduplicated V2 would differ on 1,706
product rows.

**10. Existing classification register treatment**
Each duplicate row is individually classified; there is no duplicate flag in the register
schema. Anomaly `ANOM-0027` (`DUPLICATE_TRANSACTION_ROWS`) remains `OPEN`. The register
preserves row-level evidence, which is what makes later investigation possible.

**11. Available decision alternatives**
- **A. Remove exact duplicates.**
- **B. Preserve every source record.**
- **C. Flag duplicate candidates for investigation.**
- **D. Apply deduplication only when supported by a documented business key and authoritative
  evidence.**

**12. Advantages of each alternative**
- A: immediate reduction in apparent demand; simple and deterministic.
- B: no history loss; full reconciliation to the source row count.
- C: preserves truth and creates an investigation queue; supports evidence-based resolution.
- D: the only option that is both non-destructive and analytically honest; allows metrics to
  use a deduplicated view while the ledger stays intact.

**13. Disadvantages of each alternative**
- A: destroys the ability to reconcile to 541,909 rows; irreversible without the original
  workbook; may delete genuine lines.
- B: leaves inflated metrics and no signal that a problem exists.
- C: adds a flag dimension and manual workload; without a resolution path the queue grows.
- D: requires a business key and evidence that the dataset does not yet supply; slower.

**14. Downstream consequences**
If duplicates are left unflagged, every velocity metric carries a known, unquantified
overstatement. If they are deleted, the source-to-report reconciliation breaks and the audit
trail is lost. Flagging preserves both, at the cost of two parallel measures (gross and
deduplicated) that reports must label explicitly.

**15. Interaction with dead-stock intelligence**
Duplicate inflation makes products look faster-moving than they are, which can delay a
dead-stock classification (false negative). It also inflates units-per-invoice and FSN
consumption rates. Deduplicating without flagging could instead make products look slower
(false positive). The safest approach is to compute both and report the flag.

**16. Recommended approach**
**Recommend C now and D as the target.** Add (after approval) an immutable
`duplicate_candidate` flag with the group ID and group size, preserving all rows. Use the
eight-column key as the candidate definition — it is reproducible and conservative. Do not
remove records. A deduplicated analytical view may be introduced only after the owner approves
a business key and the business confirms that exact duplicates are not legitimate repeat
lines.

**17. Risks of the recommendation**
- The eight-column key may over-flag genuine simultaneous repeat purchases (e.g. a till
  splitting a line). Keeping the flag non-destructive limits the damage.
- Two measures (gross vs deduplicated) can confuse consumers if labels are unclear.
- A future "remove duplicates" decision would need a versioned dataset, not an edit.

**18. Evidence still missing**
The source system's line-item rules, till/export behaviour, and any order-level identifier
that could distinguish a repeated line from a duplicated load. Without these, the business
key cannot be authoritative.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) that no source row may be deleted; (b) that duplicate
candidates are flagged, not removed (recommended); (c) the eight-column key as the candidate
definition; (d) whether a deduplicated analytical view should be produced, and under what
business-key evidence."

**20. Proposed approval status**
`PENDING` — owner decision required. No record has been deleted or flagged in data.

---

## 10. D05 — ZERO-PRICE TRANSACTIONS

### 20-field decision structure

**1. Decision ID and title**
D05 — Financial and physical treatment of 2,515 zero-price transactions.

**2. Exact problem statement**
2,515 rows have UnitPrice = 0. They represent £0 of revenue but −134,354 net units. Some are
almost certainly free goods or replacements (real physical movement); some are write-offs,
corrections, damages or administrative notes. The dataset has no purpose field. The owner must
decide whether zero-price rows may ever count as sales and how they enter inventory reasoning.

**3. Why the decision matters to TREXO**
A zero-price item can be real demand and real stock consumption. Excluding all zero-price rows
from inventory analysis would hide free replacements and promotional consumption; including
them in revenue would be wrong. Product demand measurement must separate *commercial* demand
from *physical* outflow.

**4. Relevant source evidence**
DIRECTLY VERIFIED:
- Total zero-price rows: **2,515**; invoices **2,155**; codes **1,419**; customers present on
  only 40 rows (2,475 missing).
- Positive quantity: **1,179** rows, +72,603 units.
- Negative quantity: **1,336** rows, −206,957 units; **all 1,336 are non-`C` invoices**.
- Zero-quantity zero-price rows: 0.
- Quantity distribution: median |qty| 12; p99 1,553.28; max 12,540; **59 rows with |qty| ≥ 1,000**.
- Descriptions: 1,454 missing; "check" 159; "?" 47; "damages" 45; "damaged" 43; "found" 25;
  "sold as set on dotcom" 20; "adjustment" 16; "thrown away" 9; "Unsaleable, destroyed." 9.
- **1,287 of the 1,419 zero-price codes also have paid sales** (90.7%), so zero price is an
  event attribute, not a product attribute.
- The 59 extreme-quantity rows are recorded as `ANOM-0002`-type HIGH anomalies (59
  `EXTREME_ZERO_PRICE_QUANTITY` anomalies).

**5. Exact affected record counts**
2,515 rows; 2,155 invoices; 1,419 codes; 1,179 positive; 1,336 negative; 59 extreme-quantity
rows; 1,454 rows without description.

**6. Affected invoices and products**
Zero-price rows appear on ordinary and cancellation-free invoices. The top codes are ordinary
product codes (23084, 35965, 20713, 22501, …), reinforcing that these are product events, not
special codes. The largest volumes are negative stock-adjustment lines.

**7. Financial impact**
£0.00 revenue by definition. Removing them from revenue changes nothing; including them as
sales would create false revenue only if a price were imputed — which must not be done. The
economic exposure is the *cost* of free units, which is unknown because acquisition cost is
absent (BLOCKED_BY_EXTERNAL_DATA).

**8. Physical inventory impact**
Potentially real and material: +72,603 units (if positive rows are physical outflows) and
−206,957 units (if negative rows are write-offs/destruction). Neither direction is proven by
the dataset. Physical impact must be `UNKNOWN` per row until evidence (description, stock
record, adjustment document) supports a direction.

**9. Current V2 treatment**
Zero-price positive rows are excluded by the price > 0 rule; zero-price negative rows are
excluded by the quantity > 0 rule. V2 therefore contains none of them, and product demand is
computed without free-goods consumption.

**10. Existing classification register treatment**
1,179 P05 rows (positive, zero price) and 1,336 P03 rows (negative, non-cancel) are ROW-level
entries. Proposals: UNKNOWN (584 P05 + 855 P03), NEEDS_MANUAL_REVIEW (587 P05 + 298 P03), plus
a small number of others. All carry `UNKNOWN_PHYSICAL_IMPACT` or `ZERO_FINANCIAL_VALUE`.
`ANOM-0002`-family and `ANOM-0009`–`ANOM-0012` remain `OPEN`.

**11. Available decision alternatives**
- **A. Exclude all zero-price records from ordinary revenue.**
- **B. Preserve zero-price physical items as potential inventory movements.**
- **C. Classify zero-price transactions according to evidence and business purpose.**
- **D. Maintain independent financial and physical movement classifications.**

**12. Advantages of each alternative**
- A: correct for revenue, trivial to apply, already the de facto V2 behaviour.
- B: prevents free goods from disappearing from inventory reasoning.
- C: allows free samples, replacements, promotions and write-offs to be distinguished.
- D: the only model that is simultaneously correct for revenue (zero) and potentially correct
  for stock (non-zero); consistent with D03's architecture.

**13. Disadvantages of each alternative**
- A: if applied to inventory too, hides real consumption; "not revenue" becomes "not movement".
- B: without purpose evidence, may treat data errors as stock movements.
- C: requires evidence the dataset largely lacks (1,454 missing descriptions).
- D: two dimensions to maintain; consumers must know which one they are reading.

**14. Downstream consequences**
Demand measurement: excluding zero-price rows understates physical consumption; including
them in revenue overstates sales. The defensible output is three measures — paid units, free
units, and total physical outflow (where evidence supports it) — with the free-units measure
labelled as unverified.

**15. Interaction with dead-stock intelligence**
Free replacements and samples consume stock and can therefore make a product *less* dead than
paid sales alone suggest. Write-offs may indicate the product is already unsaleable, which is
dead-stock evidence of a different kind. Treating all zero-price rows as noise would erase both
signals. Treating them all as demand would fabricate it.

**16. Recommended approach**
**Recommend D, with C as the resolution mechanism.** Keep revenue at zero; keep the rows out of
paid-sales metrics; carry a separate physical-movement classification that stays `UNKNOWN`
until evidence appears; route ambiguous rows to the manual queue. Never impute a price.
Never delete the rows. Report free-unit volume separately from paid demand.

**17. Risks of the recommendation**
- A large share of rows will remain `UNKNOWN` indefinitely, adding to the manual queue.
- If free units are later confirmed as physical, historical demand measures will need a
  restatement; the versioning must support that.
- The 59 extreme-quantity rows may be data errors rather than movements; they need individual
  review before any stock conclusion.

**18. Evidence still missing**
Acquisition cost (for the value of free goods), stock movement records, promotion/sample
documentation, and descriptions for 1,454 rows. The dataset cannot distinguish a sample from
a data-entry error.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) zero-price rows never count as revenue (recommended);
(b) zero-price rows are retained and may represent physical movement (recommended);
(c) physical impact remains UNKNOWN until evidence exists; (d) free-unit volume is reported
separately from paid demand."

**20. Proposed approval status**
`PENDING` — owner decision required. No zero-price row has been removed or reclassified.

---

## 11. D06 — STOCKCODE NORMALIZATION

### 20-field decision structure

**1. Decision ID and title**
D06 — Reversible canonical StockCode normalization for mixed-type identifiers.

**2. Exact problem statement**
The raw `StockCode` column is a pandas `object` column holding **487,036** Python integers and
**54,873** strings. It contains case variants (`15056BL` / `15056bl`, `M` / `m`), 37 raw codes
that fail the `\d{5}[A-Za-z]?` pattern, and 650 codes with more than one description. Any
string operation applied before casting silently ignores 487,036 rows. Any aggressive
uppercase merge silently combines 112 distinct raw codes into 112 fewer keys — some of which
may be genuinely distinct products.

**3. Why the decision matters to TREXO**
Product identity is the join key for every demand, recency and dead-stock metric. If
`15056BL` and `15056bl` remain separate, one product's history is split and its last-sale date
can be wrong. If unrelated codes are merged, two products' histories are conflated. The
normalization rule must be explicit, reversible and evidence-aware.

**4. Relevant source evidence**
DIRECTLY VERIFIED:
- Type composition: 487,036 int + 54,873 str; 0 null.
- After `astype(str).str.strip()`: 4,070 distinct codes.
- Whitespace: **0** rows.
- Lower-case rows: **1,977**, across **117** raw codes.
- Leading zeros: **0** codes matching `^0\d{4}`.
- Standard-pattern match `^\d{5}[A-Za-z]?$`: **538,524** rows; non-standard: **3,385** rows
  across **37** raw codes.
- Code lengths: 1 char ×715; 2 ×144; 3 ×710; 4 ×1,276; 5 ×487,036; 6 ×51,488; 7 ×390;
  8 ×31; 9 ×48; 12 ×71.
- Case-folding (strip + upper) yields **3,958** distinct codes → **112** keys with more than
  one original variant.
- Examples of collisions: `15056BL`/`15056bl`, `15056N`/`15056n`, `15056P`/`15056p`,
  `15060B`/`15060b`, `18098C`/`18098c`, `35809A`/`35809a`, `46776A`/`46776a`.
- V2 currently contains both `15056BL` (321 invoices, £15,828.84) and `15056bl`, i.e. one
  product split across two rows.

Note: `DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md` reports 35 non-product codes; this review counts
37 raw codes failing the pattern. The difference is a counting convention (family vs raw
variant), not a data discrepancy, and should be reconciled in the policy document.

**5. Exact affected record counts**
487,036 integer-typed values; 54,873 string-typed values; 1,977 lower-case rows; 117 lower-case
codes; 112 case-collision keys; 650 codes with multiple descriptions; 3,385 non-standard rows.

**6. Affected invoices and products**
The 112 case-collision keys affect the products whose histories would merge. `15056BL` is the
highest-value example. The 650 multi-description codes raise a separate identity question:
same code, different description may mean a renamed product or a data error.

**7. Financial impact**
Merging `15056BL`/`15056bl` combines £15,828.84 and the smaller lower-case row into one
£16,915.72 product (V2 value). Not merging understates the product's revenue and splits its
recency. The financial impact of the other 111 merges is not individually quantified; it must
be measured before any automatic merge is approved.

**8. Physical inventory impact**
Identity affects whether two rows refer to one physical product. Merging case variants of the
same physical item is likely correct; merging different items would create a phantom product.
The dataset does not include a product master, so physical identity is inferred from
description and code structure.

**9. Current V2 treatment**
V2 groups by a `CodeKey` derived from the code; `15056BL` and `15056bl` remain separate V2 rows.
The research baseline (3,898 products) is computed on V2 product rows, so it inherits this
split. The audit's `StockCodeUpper` is used for per-code analysis but does not rewrite V2.

**10. Existing classification register treatment**
Each row records its original `StockCode`; no canonical identifier is added. Anomaly
`ANOM-0036` (`STOCKCODE_CASE_VARIANTS`) remains `OPEN`. The register is therefore reversible by
construction — the original is always present — but has no governed alias table.

**11. Available decision alternatives**
- **A. Convert all codes to strings without further changes.**
- **B. Strip whitespace and normalize case.**
- **C. Create a canonical identifier while preserving the original identifier.**
- **D. Maintain a separate governed alias mapping.**

**12. Advantages of each alternative**
- A: removes the type hazard; zero information loss; trivial to validate.
- B: fixes the visible duplicates (`15056BL`); deterministic; easy to test.
- C: gives one stable join key while keeping full reversibility; supports a product master.
- D: separates identity governance from transformation; allows evidence and approval per
  alias; can accommodate genuinely distinct products that share a case-folded code.

**13. Disadvantages of each alternative**
- A: leaves one product split across two identities; metrics remain wrong for `15056BL`.
- B: merges 112 keys with no evidence; may conflate distinct products; not reversible in
  downstream joins unless the original is retained.
- C: requires defining the canonicalization rule precisely (case, whitespace, leading zeros)
  and deciding what to do with code families such as GIFT/DCGS.
- D: adds a governed artefact and process; aliases can go stale if not maintained.

**14. Downstream consequences**
Identity determines product counts (3,922 V2 rows currently, 3,898 research products, 4,070 raw
codes). It also determines last-sale dates: a split product can appear to have an older last
sale than it truly has, creating a false dead-stock signal. Conversely, an over-merge can
combine a live product with a dead one and hide the dead one.

**15. Interaction with dead-stock intelligence**
This is the highest-leverage identity decision for false positives. `15056BL` is a fast-moving
product with a sale on the last day of the dataset; if its history is split, one variant may
look inactive. Merging unrelated codes could make a dead product inherit another's recent
sale. Reversibility and per-alias governance are therefore essential.

**16. Recommended approach**
**Recommend C + D.** Always cast to string first (mandatory, because of the 487k integer
values), strip whitespace, and create a canonical key — but never overwrite the original.
Store the mapping in a governed alias table with, per alias: original code, canonical code,
evidence (description equality, price consistency, owner confirmation), approval status and
effective date. Default behaviour: do **not** merge beyond exact string equality plus
whitespace/case folding until each collision is reviewed. Keep GIFT/DCGS families keyed
individually, not collapsed to a family.

**17. Risks of the recommendation**
- An alias table is another governed asset that must be maintained; without an owner it
  becomes stale.
- Case folding is safe for the 112 observed collisions only if descriptions agree; 650 codes
  already have multiple descriptions, so evidence must be checked per pair.
- Some codes are numeric-looking but semantically strings (e.g. `10002` as int vs `"10002"`);
  the canonical key must preserve the five-digit format including any leading zeros — none are
  currently observed, but the rule must not assume that.

**18. Evidence still missing**
A product master or supplier catalogue that confirms which case variants are the same physical
item. Also missing: an explanation for the 650 multi-description codes. No leading-zero codes
exist today, but the rule must be future-proof.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) string-cast + strip as mandatory preprocessing;
(b) case folding as the default canonicalization (recommended) or review-before-merge;
(c) the canonical-ID + preserved-original model; (d) whether a governed alias table is
required; (e) who approves a merge."

**20. Proposed approval status**
`PENDING` — owner decision required. No normalization has been implemented.

---

## 12. D07 — UNKNOWN AND NEEDS_MANUAL_REVIEW

### 20-field decision structure

**1. Decision ID and title**
D07 — Governance of unresolved classifications (`UNKNOWN` and `NEEDS_MANUAL_REVIEW`).

**2. Exact problem statement**
The register reports 1,439 `UNKNOWN`, 1,581 `NEEDS_MANUAL_REVIEW` and 3,025 rows with
`ManualReviewRequired=YES`. The three numbers do not add up because they are different fields:
category, category, and a flag. The owner must decide how uncertainty is held, who resolves it,
and how unresolved rows affect downstream metrics.

**3. Why the decision matters to TREXO**
Uncertainty that disappears through automation is worse than visible uncertainty. If
`UNKNOWN` rows are forced into a category, TREXO will report confident but false demand and
dead-stock signals. If they are excluded entirely, product histories become incomplete. The
policy must keep uncertainty visible, quantified and resolvable with evidence.

**4. Relevant source evidence**
DIRECTLY VERIFIED from the register:
- `ProposedCategory = UNKNOWN`: **1,439**. Every one has `ConfidenceLevel = UNKNOWN` and
  `ManualReviewRequired = YES`.
- `ProposedCategory = NEEDS_MANUAL_REVIEW`: **1,581** (676 LOW, 905 MEDIUM confidence).
- `ManualReviewRequired = YES`: **3,025** = 1,581 + 1,439 + **5** `FINANCIAL_ADJUSTMENT` rows
  (4 LOW + 1 MEDIUM). This is the exact reason the counts are non-additive.
- UNKNOWN by partition: P03 negative non-cancel 855; P05 positive zero-price 584.
- NEEDS_MANUAL_REVIEW by partition: P05 587; P07 paid 391; P01 cancellation 305; P03 298.
- Manual-review rows: 1,581 NEEDS_MANUAL_REVIEW + 1,439 UNKNOWN + 5 FINANCIAL_ADJUSTMENT.

**5. Exact affected record counts**
1,439 UNKNOWN + 1,581 NEEDS_MANUAL_REVIEW + 5 flagged financial adjustments = **3,025**
manual-review rows. This is 0.56% of the 541,909 source rows but 20.6% of the 14,684 register
entries, because unresolved rows are always row-level (RowCount 1). By row coverage, the 3,025
manual-review entries represent 3,025 source rows.

**6. Affected invoices and products**
Spread across P01, P03, P05 and P07. The P05 group (zero-price) and P03 group (negative
non-cancel) dominate, which is consistent with the D03/D05 evidence gaps. P07 manual-review
rows (391) are the most concerning: they are paid sales whose business meaning is unclear.

**7. Financial impact**
Not directly quantifiable as a single number in the register (no value field). The unresolved
P07 rows carry revenue, so their misclassification could affect product revenue; the P05/P03
groups carry zero revenue. A precise value would require joining the register to source rows;
this pack does not claim one.

**8. Physical inventory impact**
All 3,025 carry `UNKNOWN_PHYSICAL_IMPACT` (except the 5 financial adjustments, which are
`NO_PHYSICAL_STOCK_MOVEMENT` or unknown). By definition, physical impact is unresolved.

**9. Current V2 treatment**
V2 ignores the register: it uses only the sale definition. UNKNOWN rows that satisfy the sale
definition (391 P07 rows) are counted as sales; UNKNOWN rows outside it are not. So V2 is
"confidently" including rows the classification says are unresolved.

**10. Existing classification register treatment**
This is the mechanism itself: 3,025 rows are marked `PROPOSED_PENDING_MANUAL_REVIEW`; the
remaining 11,657 ROW entries and 2 GROUP entries are `PROPOSED_ROW_LEVEL` /
`PROPOSED_GROUP_LEVEL`. No row is `APPROVED`. Anomalies relating to ambiguity remain `OPEN`.

**11. Available decision alternatives**
- **A. Force all records into the closest available category.**
- **B. Preserve UNKNOWN indefinitely until evidence appears.**
- **C. Maintain a formal manual-review queue.**
- **D. Introduce evidence-based resolution workflows with immutable audit history.**

**12. Advantages of each alternative**
- A: produces a complete, tidy dataset; simple downstream logic.
- B: never fabricates certainty; preserves the audit truth.
- C: makes the work visible and assignable; supports prioritisation.
- D: combines B and C with traceability — every resolution records who, when, on what
  evidence, and what changed.

**13. Disadvantages of each alternative**
- A: the worst option — uncertainty vanishes without evidence; violates the governance
  principle directly.
- B: without a queue, "indefinitely" becomes "never"; metrics carry permanent blind spots.
- C: a queue without audit history can be edited silently; no learning.
- D: the most process-heavy; requires ownership, tooling and discipline.

**14. Downstream consequences**
Every metric built on V2 currently treats 391 unresolved paid rows as certain sales. Product
confidence should be degraded where unresolved rows are material. Dead-stock classifications
should be marked "provisional" for affected products rather than presented as final.

**15. Interaction with dead-stock intelligence**
Unresolved rows can either hide demand (if they are real sales not counted) or invent it (if
they are adjustments counted as sales). The correct treatment is a confidence qualifier on the
product assessment, not a silent inclusion or exclusion. Products whose history is materially
unresolved should be flagged `PROVISIONAL` in any dead-stock output.

**16. Recommended approach**
**Recommend D, operationalised through C.** Keep `UNKNOWN` as a permanent, legal state (B is
a necessary invariant); add a review queue with priority (value at stake, physical ambiguity,
product criticality); require evidence and an immutable audit record for any resolution; never
allow a bulk "resolve all" action. Unresolved rows remain in the ledger and are excluded from
*confident* product claims, not from the data.

**17. Risks of the recommendation**
- The queue may never clear; that is acceptable if it is visible and prioritised.
- Resolution quality depends on evidence availability, which is external.
- A future automation could reintroduce "force to nearest category"; the policy must prohibit
  it explicitly.

**18. Evidence still missing**
Business definitions for the ambiguous descriptions; promotion/sample records; accounting
documentation; and a product master. For the 391 P07 rows, the key missing evidence is what
the line actually represents commercially.

**19. Exact decision required from the project owner**
"Approve, reject, modify or defer: (a) `UNKNOWN` remains a permanent legal state;
(b) a formal manual-review queue is maintained; (c) every resolution requires evidence and an
immutable audit record; (d) unresolved rows degrade confidence in downstream metrics rather
than being forced or dropped; (e) who owns the queue."

**20. Proposed approval status**
`PENDING` — owner decision required. All 3,025 rows remain unresolved.

---

## 13. REGISTER COVERAGE AUDIT

### 13.1 What the register is

`reports/transaction_classification_register_v1.csv` is a *hybrid* evidence register:
14,684 entries covering 541,909 source rows. It is not a one-row-per-transaction table, and it
is not a summary table. It mixes two scope levels by design:

| ScopeLevel | Entries | RowCount semantics | SourceRow semantics |
|---|---|---|---|
| `ROW` | **14,682** | always 1 | the exact source row number (`SourceRowScope=EXACT`) |
| `GROUP` | **2** | number of source rows represented | a representative row (`SourceRowScope=REPRESENTATIVE_OF_GROUP`) |

### 13.2 Why GROUP entries exist

The register's own construction rule (verified in
`src/trexo/audit_special_transactions.py`, `build_classification_register`) is:

- Emit a ROW entry for **every** row outside the ordinary paid partition (`P07`), **every** row
  with a non-standard StockCode, and **every** row with `|Quantity| ≥ 1000`.
- Every remaining row — ordinary paid, standard code, `|Quantity| < 1000` — is covered by
  GROUP entries, grouped by the eight classification attributes (`AuditPartition`,
  `ClassificationRule`, `ProposedCategory`, `ConfidenceLevel`, `PhysicalInventoryImpact`,
  `FinancialImpact`, `ManualReviewRequired`, `InUnusualInvoice`).

Because the row-level predicate is deterministic, the two sets are disjoint by construction.
The GROUP level is an evidence-compression device for homogeneous, low-risk sale rows; it is
not a way to avoid classifying them.

### 13.3 Independent coverage proof

DIRECTLY VERIFIED this review:

| Check | Result |
|---|---|
| Register entries | 14,684 (14,682 ROW + 2 GROUP) |
| ROW entries | 14,682 |
| ROW `RowCount` sum | 14,682 |
| GROUP entries | 2 |
| GROUP `RowCount` values | **514,016** and **13,211** |
| GROUP `RowCount` sum | 527,227 |
| Total `RowCount` | **541,909** |
| Source dataset rows | **541,909** |
| ROW `SourceRow` uniqueness | 14,682 unique / 14,682 entries |
| Duplicate exact SourceRow entries | **0** |
| All `RegisterID` unique | 14,684 / 14,684 |
| ROW `SourceRow` range | 47 … 541,770 |
| Rows not covered by ROW entries | 527,227 |
| GROUP sum vs uncovered rows | **527,227 = 527,227** |
| Row/GROUP set overlap | **0** |

The two GROUP entries are `REG-014683` (RowCount 514,016, representative SourceRow 2, invoice
536365) and `REG-014684` (RowCount 13,211, representative SourceRow 2187, invoice 536569), both
`CUSTOMER_SALE`.

### 13.4 Membership reconstruction

The register does not enumerate which source rows belong to each GROUP; it records only a
representative. To test the claim independently, this review re-derived the row-level
predicate from the raw data and applied it:

- Rows meeting the ROW predicate: **14,682** — exactly the register's ROW count.
- Remaining rows: **527,227** — exactly the sum of the two GROUP `RowCount` values.
- Every remaining row is in partition `P07`, has a standard code, and has `|Quantity| ≤ 992`
  (below the 1,000 threshold). No zero-price, negative-price or cancellation row is hidden
  in a GROUP.
- Splitting the remaining rows by whether their invoice appears in
  `reports/unusual_invoice_details_v1.csv` yields **514,016** and **13,211** — exactly the two
  GROUP `RowCount` values.

**Conclusion:** coverage is exact at the cardinality level and reconstructible at the
membership level using the documented predicate. Every source row is accounted for exactly
once. This is a proof of the coverage identity, not a proof that each classification is
correct.

### 13.5 Evidence preservation — the limitation

GROUP entries preserve: the classification attributes, the evidence text, the confidence
explanation and one representative row. They do **not** preserve a per-row listing of which
SourceRows are in the group. Consequences:

- A GROUP classification can be audited to its rule and representative example, but not
  row-by-row without re-running the predicate.
- If the classification rule changes, the GROUP composition changes and the register must be
  regenerated (which is exactly what change control requires).
- Any downstream claim about an individual GROUP row must go back to the source workbook.

This is an acceptable trade-off for 527,227 homogeneous sale rows, but it must be stated in
the policy: **GROUP-level evidence is rule-level and representative, not transaction-level.**

### 13.6 What this audit does not do

It does not modify the register, reclassify any row, or assert that the proposed categories are
correct. Those are owner decisions (D01–D07).

---

## 14. CROSS-DECISION DEPENDENCY MATRIX

### 14.1 How to read the matrix

`BLOCKS` = the decision must be settled before the dependent capability can be trusted.
`PARTIAL` = the capability can run but its output must carry a caveat.
`—` = no material dependency.

| Decision | Depends on | Metrics affected | Reports affected | Blocks V3 | Blocks historical dead-stock | Blocks current dead-stock | Blocks financial exposure |
|---|---|---|---|---|---|---|---|
| **D01** Bad debt | D02 (code classification) | Revenue, ASP, value-based ABC, product count | V2, audit, dead-stock value ranking | **YES** | PARTIAL | PARTIAL | **YES** |
| **D02** Non-product codes | D06 (identity) | Product count, revenue, quantity, ABC/FSN population | V2, stockcode analysis, dead-stock population | **YES** | **YES** | PARTIAL | **YES** |
| **D03** Cancellation/return | D07 (ambiguity) | Net quantity, return rate, velocity, stock flow | Audit, demand metrics | **YES** | PARTIAL | PARTIAL | PARTIAL |
| **D04** Duplicates | D06 (key stability) | Units, velocity, invoice frequency, FSN rate | V2, demand metrics | PARTIAL | PARTIAL | — | PARTIAL |
| **D05** Zero price | D03, D07 | Physical demand, free-unit volume, stock flow | Demand metrics, dead-stock evidence | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| **D06** Normalization | D02 (product/product-family boundary) | Product count, last-sale date, recency, ABC/FSN | All product-level outputs | **YES** | **YES** | PARTIAL | PARTIAL |
| **D07** Unknown/manual | D03, D05 | Confidence of every product metric | All outputs (confidence qualifiers) | PARTIAL | PARTIAL | PARTIAL | PARTIAL |

### 14.2 Blocking chains

1. **D06 → D02 → D01.** Identity must be stable before a code registry can be authoritative,
   and the registry must exist before the bad-debt code can be formally excluded. A V3 built
   before this chain is settled would encode a guessed product boundary.
2. **D03 → D05 → D07.** Negative quantities and zero prices are the two largest sources of
   ambiguity; both feed the manual-review queue. Resolving the queue without D03/D05 rules
   would produce arbitrary labels.
3. **D04 → D03.** A cancellation/reversal pair is *not* an exact duplicate (different invoice,
   different sign), so duplicate handling must not be allowed to absorb reversals. The
   eight-column key already separates them (only 69 duplicate rows are cancellations).

### 14.3 Ranked importance (qualitative, no invented scores)

Ranking criteria, applied in this order: data-integrity risk → financial impact → inventory
impact → downstream dependency → urgency.

1. **D02 — non-product codes.** Largest financial contamination (£412,565.65) and the broadest
   effect on the product population. Deciding it wrong either deletes a real product or keeps
   services in every ranking.
2. **D06 — normalization.** Identity errors create false dead-stock signals in both directions
   and propagate to every product-level output. It gates D02.
3. **D01 — bad debt.** Small row count, CRITICAL severity, clean £11,062.06 revenue error and a
   direct test of the financial-vs-physical principle.
4. **D03 — cancellation/return.** Large population (10,624 rows), but V2 already excludes them;
   the risk is in *interpreting* them, not in current totals.
5. **D04 — duplicates.** Known, quantified inflation (£21,740.98 / 15,956 units), contained by
   flagging; can run in parallel with the others.
6. **D05 — zero price.** Zero revenue, but material physical ambiguity and a large manual-review
   load.
7. **D07 — unknown/manual.** Not a separate data problem; it is the governance mechanism that
   the other six decisions feed. It should be designed first even though it ranks last on
   financial impact.

No numerical priority score is assigned because no defensible weighting has been approved.

---

## 15. DEAD-STOCK INTELLIGENCE IMPACT

### 15.1 Five concepts that must not be conflated

| Concept | Definition used here | Evidence required | Current status |
|---|---|---|---|
| A. Historical sales inactivity | No observed sale in a defined historical window | Sales history only | **Computable, conditional on D01–D07** |
| B. Current non-moving inventory | Stock on hand that has not moved in a period | Stock snapshot + movements | **BLOCKED_BY_EXTERNAL_DATA** |
| C. Actual dead stock | Approved business definition applied to real stock | B + owner-approved rule | **BLOCKED_BY_APPROVAL + DATA** |
| D. Future dead-stock risk | Forward-looking risk from demand, coverage, lifecycle | A + B + forecast inputs | **NOT_IMPLEMENTED / blocked** |
| E. Financially trapped inventory | Value of stock unlikely to sell | C + acquisition cost | **BLOCKED_BY_EXTERNAL_DATA** |

TREXO may report A today. It may not report B–E as facts.

### 15.2 Measured baseline (from the research, not recomputed here)

These figures are quoted from `docs/DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md` and are **not**
independently recomputed in this pack (labelled accordingly):

- 527,342 V2 sale rows on product codes; **3,898 products**; £10,254,118.89 line value.
- 460 products with no sale in the final 180 days (11.80%), 55,623 units, £103,128.42 of
  *historical* line value.
- ABC: A = 543, B = 791, C = 2,564. FSN: 2,830 fast (≥20 invoices), 632 slow (5–19), 436
  non-moving (<5).
- 677 products with no sale in the final 90 days.

These are sales-side facts about one historical year. They rank past behaviour; they do not
establish any current stock position.

### 15.3 Decision → metric trust table

| Metric / capability | Required decisions | Current status | Why |
|---|---|---|---|
| Product count | D02, D06 | **CONDITIONALLY_READY** | Depends on whether services and case variants are products |
| Historical revenue | D01, D02 | **CONDITIONALLY_READY** | £11,062.06 bad debt + £412,565.65 non-product value |
| Last observed sale date | D06, D02 | **CONDITIONALLY_READY** | Split identities can move last-sale dates |
| Sales frequency / velocity | D04, D06 | **CONDITIONALLY_READY** | 5,268 duplicate rows inflate counts |
| Units sold | D04, D05 | **CONDITIONALLY_READY** | Duplicates and free goods |
| Demand variability / XYZ | D01–D07 | **CONDITIONALLY_READY** | Inherits all upstream errors |
| ABC by value | D01, D02 | **CONDITIONALLY_READY** | Non-product value distorts thresholds |
| ABC by units | D04, D05 | **CONDITIONALLY_READY** | Duplicates / free units |
| FSN | D02, D04, D06 | **CONDITIONALLY_READY** | Invoice counts depend on all three |
| Historical inactivity (180d) | D02, D06 | **CONDITIONALLY_READY** | Product boundary and identity |
| Current non-moving stock | external inventory | **BLOCKED_BY_DATA** | No snapshot |
| Inventory ageing | receipts data | **BLOCKED_BY_DATA** | No receipt dates |
| Actual dead stock | owner definition + stock | **BLOCKED_BY_APPROVAL + DATA** | Not derivable from sales |
| Future dead-stock risk | A + B + model | **NOT_IMPLEMENTED** | No approved rule or data |
| Financial exposure | cost + stock | **BLOCKED_BY_DATA** | No acquisition cost |
| Recovery effectiveness | outcomes history | **NOT_IMPLEMENTED** | No pilot data |

### 15.4 What changes if the recommendations are approved

- Approving D01 removes a £11,062.06 phantom product sale.
- Approving D02 (registry + separation) moves product revenue from £10.25m toward £9.84m and
  removes service codes from the dead-stock population, while preserving `15056BL`.
- Approving D06 merges `15056BL`/`15056bl`, which can change that product's last-sale date and
  therefore its inactivity status.
- Approving D04 as "flag, don't delete" leaves headline metrics unchanged but adds a
  deduplicated view; the difference is £24,573.74 in V2 value.
- Approving D03/D05 does not change V2 totals (those rows are already excluded) but changes
  what TREXO is allowed to *claim* about demand and stock.

### 15.5 Hard rule for all future outputs

A product with zero recent sales and no stock record must be labelled **"no observed sale in
the period"**, never **"dead stock"**. Any dead-stock label requires the owner-approved
definition in §15.1 and evidence of current stock.

---

## 16. EVIDENCE AND CONFIDENCE ASSESSMENT

### 16.1 Evidence summary by decision

| Decision | Evidence supporting the recommendation | Evidence against / complicating | Missing evidence | Overall evidential position |
|---|---|---|---|---|
| D01 | Positive row meets V2 rule; two offsetting negative-price rows; no customer, no product, "Adjust bad debt"; group nets to −£11,062.06 | The two credits are unexplained; a real sale-and-credit could in principle look similar | Accounting ledger; confirmation `B` is administrative | **STRONGLY INFERRED** that it is a financial event; **UNRESOLVED** why two credits |
| D02 | Per-code values reproduced; `15056BL` has product description and 2,844 units; services have no physical evidence | `M`, `S`, `PADS`, `DCGS*` are ambiguous; some may be physical | Product master; business meaning of ambiguous families | **DIRECTLY VERIFIED** figures; **STRONGLY INFERRED** classification for most; **UNRESOLVED** for M/S/PADS/DCGS |
| D03 | All 1,336 non-C negative rows are zero-price and use write-off language; 95.6% of cancellations match a prior sale | Matching is customer+code+date, not an order link; 406 unmatched; no stock record | Returns/credit notes; order IDs | **DIRECTLY VERIFIED** counts; **STRONGLY INFERRED** that non-C rows are adjustments; **UNRESOLVED** physical direction |
| D04 | Exact 8-column duplicates: 5,268; 4,879 groups; identical timestamps; 5,226 in V2 | Simultaneous repeat lines can be legitimate; 20-row group suggests a load artefact but is not proof | Source-system export rules; order IDs | **DIRECTLY VERIFIED** counts; **STRONGLY INFERRED** data duplication; **UNRESOLVED** per-row truth |
| D05 | 2,515 rows, 1,179/1,336 split; 1,287/1,419 codes also have paid sales; write-off descriptions | 1,454 rows have no description; free goods vs errors indistinguishable | Cost, stock records, promotion records | **DIRECTLY VERIFIED** counts; **WEAKLY INFERRED** purpose; **UNRESOLVED** physical impact |
| D06 | Type composition 487,036/54,873; 112 case collisions; 650 multi-description codes; `15056BL` split in V2 | Some case variants may be distinct products; no product master | Product master / alias confirmation | **DIRECTLY VERIFIED** figures; **STRONGLY INFERRED** that case folding is correct for most; **UNRESOLVED** per-pair |
| D07 | Field-level arithmetic: 3,025 = 1,581 + 1,439 + 5; partitions identified | None — this is arithmetic, not interpretation | Resolution evidence for each of 3,025 rows | **DIRECTLY VERIFIED** |

### 16.2 Assumptions made in this pack

1. The raw workbook is the authoritative source and is unchanged (hash-verified).
2. `SourceRow = Excel data row + 1` (row 2 is the first data row), consistent with the audit.
3. V2's sale definition is exactly: invoice not starting with `C`, quantity > 0, unit price > 0.
4. The register's `RowCount` is the number of source rows represented by an entry.
5. `special_stockcode_analysis_v1.csv` aggregates case variants of the same code family.
6. Financial values are unrounded float64; two-decimal display is presentational only.

### 16.3 Confidence statements (evidence, not labels)

- The coverage identity (541,909) is a **mathematical** result, verified twice, not an opinion.
- The per-code values are **reproducible** from the workbook and the published CSV; the three
  spotlight figures (£16,915.72, £685.81, £398.45) were independently recomputed and match.
- The *meaning* of the ambiguous codes and the *physical direction* of negative/zero-price rows
  remain **unresolved**; no amount of re-computation will settle them without external records.
- The duplicate *existence* is proven; the duplicate *cause* is not.

---

## 17. CONSOLIDATED DECISION REGISTER

**Every approval status is `PENDING`. No decision is preselected.**

### 17.1 Summary register

| ID | Decision | Current status | Recommended option | Alternatives | Financial impact | Inventory impact | Downstream dependency | Evidence gap | Owner decision | Approval status |
|---|---|---|---|---|---|---|---|---|---|---|
| D01 | Bad-debt group A563185–A563187 / code `B` | Positive row counted in V2 (£11,062.06); negatives excluded | D now, C as target: exclude group from product analytics, preserve financial event | A retain; B exclude group; C separate ledger; D raw + analytical exclusion | £11,062.06 overstated product revenue; group net −£11,062.06 | None proven | D02, D06; blocks V3 revenue | Accounting ledger; `B` confirmation | Approve / Reject / Modify / Defer | **PENDING** |
| D02 | Non-product / non-standard codes in V2 | All sale-qualifying codes aggregated as products | C + D: governed code registry + separated analytical views | A exclude all; B exclude financial/service only; C registry; D views | £412,565.65 non-product value; £16,915.72 real product at risk | Mixed; `15056BL` physical | D06; blocks V3, product count, ABC | Product master; meaning of M/S/PADS/DCGS | Approve / Reject / Modify / Defer | **PENDING** |
| D03 | Cancellation vs return vs write-off | C-prefix excluded from V2; non-C negatives excluded by sign | D: three dimensions (event / financial / physical) | A all cancellation; B all returns; C separate labels; D multi-dimensional | £896,812.49 cancellation value; £0 on 1,336 adjustments | Unproven both directions | D07; blocks net demand | Returns records; order linkage | Approve / Reject / Modify / Defer | **PENDING** |
| D04 | 5,268 duplicate rows | Included in V2 | C now, D as target: flag, never delete | A remove; B preserve; C flag; D evidence-based dedupe | £21,740.98; £24,573.74 in V2 | Unknown | D06; blocks velocity accuracy | Source export rules; order IDs | Approve / Reject / Modify / Defer | **PENDING** |
| D05 | 2,515 zero-price rows | Excluded from V2 | D + C: separate financial (zero) and physical (unknown) | A exclude from revenue; B preserve as movement; C classify by purpose; D independent dimensions | £0 revenue; free-unit cost unknown | Potentially material (±units) | D03, D07; blocks physical demand | Cost, stock records, 1,454 descriptions | Approve / Reject / Modify / Defer | **PENDING** |
| D06 | Mixed-type / case-variant codes | Raw mixed; V2 splits `15056BL` | C + D: canonical ID + preserved original + governed alias table | A cast to string; B strip + case; C canonical + original; D alias table | £16,915.72 product split | Identity affects physical grouping | D02; blocks every product output | Product master; 650 multi-description codes | Approve / Reject / Modify / Defer | **PENDING** |
| D07 | UNKNOWN / NEEDS_MANUAL_REVIEW | 3,025 rows pending; no resolution workflow | D + C: permanent UNKNOWN + queue + immutable audit | A force; B preserve; C queue; D workflow | Not quantified | Unknown | D03, D05; confidence qualifier | Per-row resolution evidence | Approve / Reject / Modify / Defer | **PENDING** |

### 17.2 Status vocabulary

| Status | Meaning in this pack |
|---|---|
| `PENDING` | Awaiting the owner's explicit response |
| `APPROVED` | **Not used** — no owner response has been received |
| `DEFERRED` | Not used |

### 17.3 What approval would and would not authorise

Approval of a recommendation authorises a *rule*, not an implementation. Even after approval,
V3 creation, script changes and register regeneration require a separate, versioned change
under the policy's change-control section. The pack does not pre-authorise any of that.

---

## 18. OUTSTANDING EVIDENCE REQUESTS

Grouped by who can supply the evidence. None of these blocks the owner's ability to decide
the *policy*; they block confirmation of the *facts*.

### 18.1 Finance / accounting

| # | Request | Resolves | Current position |
|---|---|---|---|
| E01 | Ledger/journal entry for A563185–A563187, including why two credits | D01 | UNRESOLVED |
| E02 | Confirmation that `B` is an administrative code, not a product | D01 | STRONGLY INFERRED |
| E03 | Definition of `AMAZONFEE`, `BANK CHARGES`, `CRUK`, `D` postings | D02 | Financial nature inferred |
| E04 | Whether GIFT vouchers are liabilities or goods | D02 | Voucher inferred |

### 18.2 Operations / warehouse

| # | Request | Resolves | Current position |
|---|---|---|---|
| E05 | Returns process: which `C` invoices represent physical returns | D03 | UNRESOLVED |
| E06 | Meaning of zero-price negative rows ("damages", "destroyed", "found") | D03, D05 | STRONGLY INFERRED write-off |
| E07 | Stock movement records for free/sample goods | D05 | UNRESOLVED |
| E08 | Whether `S`, `PADS`, `DCGS*` are physical stock | D02, D05 | UNRESOLVED |

### 18.3 Product / merchandising

| # | Request | Resolves | Current position |
|---|---|---|---|
| E09 | Product master confirming `15056BL` and its case variants | D02, D06 | Product confirmed by description |
| E10 | Explanation for 650 codes with multiple descriptions | D06 | UNRESOLVED |
| E11 | Meaning of `M` / `m` "Manual" | D02 | UNRESOLVED |

### 18.4 Data engineering

| # | Request | Resolves | Current position |
|---|---|---|---|
| E12 | Source-system export rules that could create exact duplicates | D04 | UNRESOLVED |
| E13 | Order/line identifiers, if they exist outside this extract | D03, D04 | Not in dataset |
| E14 | Acquisition cost and stock-on-hand (for any financial exposure) | Dead-stock B–E | Not in dataset |

---

## 19. FINAL PROJECT-OWNER APPROVAL CHECKLIST

The owner should be able to answer each line with **Approve / Reject / Modify / Defer /
Needs more evidence**. No line is pre-filled.

### 19.1 Per-decision checklist

- [ ] **D01** — Confirm `B` is administrative; exclude the A563185–A563187 group from product
      analytics; preserve the net financial effect separately.
- [ ] **D02** — Confirm product movement = physical merchandise only; approve the initial
      code-family classification; approve a governed code registry; confirm `15056BL` is a
      product and must be retained.
- [ ] **D03** — Approve the three-dimension model; confirm sign alone never means return;
      confirm no cancellation counts as stock without a stock record; choose the net-demand
      reporting convention.
- [ ] **D04** — Confirm no source row is deleted; approve flagging; approve the eight-column
      candidate key; decide whether a deduplicated view is authorised.
- [ ] **D05** — Confirm zero price never means revenue; confirm zero-price rows may represent
      physical movement; confirm physical impact stays unknown without evidence; approve
      separate free-unit reporting.
- [ ] **D06** — Approve string-cast + strip; choose case folding vs review-before-merge;
      approve canonical-ID-plus-original; approve the alias table and its approver.
- [ ] **D07** — Confirm `UNKNOWN` is permanent and legal; approve the manual-review queue;
      require immutable audit history; approve confidence qualifiers downstream; name the
      queue owner.

### 19.2 Cross-cutting checklist

- [ ] Accept that financial impact and physical movement are separate dimensions.
- [ ] Accept that historical inactivity is not current dead stock.
- [ ] Accept that V3 remains blocked until D01–D07 are answered.
- [ ] Accept that no data will be deleted, rewritten or silently normalized.
- [ ] Name the owner of the manual-review queue.
- [ ] Name the approver of product-identity aliases.
- [ ] Confirm the evidence requests in §18 that the business can supply.

### 19.3 Sign-off block (to be completed by the owner)

| Field | Value |
|---|---|
| Owner name | ______________________ |
| Date | ______________________ |
| Decisions approved | ______________________ |
| Decisions rejected | ______________________ |
| Decisions modified | ______________________ |
| Decisions deferred | ______________________ |
| Conditions attached | ______________________ |
| Signature | ______________________ |

Until this block is completed, every decision remains `PENDING`.

---

## 20. FINAL RECOMMENDATIONS

### 20.1 Technical recommendations (not approvals)

1. **Adopt D01 option D immediately as a design principle, C as the target.** Keep the
   bad-debt event intact in the ledger; exclude the whole group from product analytics;
   preserve the net −£11,062.06 in a financial view.
2. **Adopt D02 C+D.** Build a governed code registry; never blanket-exclude non-standard
   codes; retain `15056BL`; mark M/S/PADS/DCGS as unresolved rather than guessed.
3. **Adopt D03 D.** Separate event, financial and physical dimensions; treat quantity sign as
   evidence, not classification.
4. **Adopt D04 C, with D gated on evidence.** Flag 5,268 candidates; delete nothing;
   deduplicate only under an owner-approved business key.
5. **Adopt D05 D.** Zero revenue, unknown physical impact, separate free-unit reporting; never
   impute a price.
6. **Adopt D06 C+D.** Cast, strip, canonicalize reversibly, govern aliases; no default merge.
7. **Adopt D07 D.** Permanent `UNKNOWN`, a real queue, immutable audit, confidence qualifiers.

### 20.2 Sequencing

If the owner wishes to minimise rework, the dependency chain suggests this order:

1. **D06** (identity) → 2. **D02** (product boundary) → 3. **D01** (financial exclusion) →
4. **D03** (negative-event semantics) → 5. **D05** (zero-price physical) → 6. **D04**
(duplicates) → 7. **D07** (queue operation, which runs continuously from step 1).

This is a technical sequencing recommendation, not a business priority. The owner may decide
any subset in any order.

### 20.3 What must not happen

- No V3 before the decisions, and no V3 that silently embeds a recommendation.
- No deletion of duplicates, cancellations or zero-price rows.
- No forced resolution of `UNKNOWN`.
- No "current dead stock" claim from this dataset.
- No conversion of this pack into an approved rule without the sign-off in §19.3.

### 20.4 Closing statement

The transaction foundation is measurable, reconcilable and — within its limits — trustworthy.
Its remaining weaknesses are known, quantified and confined to seven decisions. The evidence
supports the recommendations above, but the evidence does not make the business decision.
TREXO should proceed only when the owner has answered D01–D07 explicitly, and every subsequent
change should be traceable to that answer.

**Every number in this pack is traceable to a named artefact or a reproducible computation.
Every recommendation is reviewable. Every business decision remains under owner control.**

---

### Appendix A — Reproduction notes

- Raw workbook read with `pandas.read_excel(..., sheet_name="Online Retail")`;
  `SourceRow = index + 2`.
- Sale definition: `InvoiceNo` not starting with `C` AND `Quantity > 0` AND `UnitPrice > 0`.
- Duplicate key: the eight source columns; `keep="first"` for extra-row counts.
- Standard code pattern: `^\d{5}[A-Za-z]?$`.
- Register coverage: `RowCount` sum; ROW `SourceRow` uniqueness; predicate reconstruction.
- All diagnostic scripts were written outside the repository
  (`C:\Users\naman\AppData\Local\Temp\opencode\`) and are not part of the deliverable.
- Protected hashes were re-checked after writing this document; see the final execution report.

### Appendix B — Figures explicitly not reverified in this pack

| Figure | Source | Status |
|---|---|---|
| 3,898 products; 460 >180 days; ABC 543/791/2,564; FSN 2,830/632/436 | `DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md` | Quoted, not recomputed |
| 527,342 V2 sale rows; £10,254,118.89 | Same | Quoted, not recomputed |
| 93 anomalies by severity | `special_transaction_anomalies_v1.csv` | Read, not re-audited |
| 41/41 test result | Previous phase report | Not re-run in this review |
