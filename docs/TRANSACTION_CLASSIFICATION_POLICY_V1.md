# TREXO — Transaction Classification Policy V1

**Status:** PROPOSAL — awaiting review. Not a final business rule set.
**Scope:** `data/raw/Online Retail.xlsx` (541,909 rows), as audited by `src/trexo/audit_special_transactions.py`.
**Companion artefacts:**
`reports/special_transaction_audit_v1.md`,
`reports/transaction_classification_register_v1.csv`,
`reports/special_transaction_anomalies_v1.csv`,
`tests/test_audit_special_transactions.py`.

This document defines the classification taxonomy, the ordered evidence rules,
the confidence model, the evidence standards, and every known divergence from
the earlier `src/trexo/classify_transaction_types.py` patterns. Nothing in it
has been approved as a production rule; approval is requested at the gate
described in section 12.

---

## 1. Governing principles

1. **Evidence before interpretation.** Every classification must cite the
   field(s) of the same row that support it. Interpretations that require
   knowledge outside the dataset (payment, shipment, warehouse, ledger) are
   recorded as contradictions or limitations, never as facts.
2. **No silent loss.** Every one of the 541,909 source rows receives exactly
   one classification entry. Rows are never deleted, merged away, or dropped
   for being inconvenient.
3. **UNKNOWN is a valid result.** A row with no usable evidence keeps
   `UNKNOWN`. UNKNOWN is never converted into a plausible-sounding category.
4. **Financial ≠ physical.** A price or amount never implies that stock moved,
   and a quantity sign never implies money moved. The two dimensions are
   classified independently (`ProposedCategory` vs `PhysicalInventoryImpact`).
5. **Negative quantity ≠ customer return.** Nothing in this dataset links a
   negative row to an original order or a customer receipt, so returns are
   never asserted.
6. **Zero price ≠ ordinary sale.** A zero price proves the item was not sold
   at a price; it does not prove gift, promo, sample, correction or error.
7. **Proposals only.** The script assigns `PROPOSED_*` statuses. Anomaly
   resolution, rule promotion, and dataset changes all require human approval.

## 2. Two-layer model: measurement partitions vs business classification

**Layer 1 — audit partitions** (`AuditPartition`, 8 labels) are pure
measurements computed from `InvoiceNo`, `Quantity`, `UnitPrice`. They are
mutually exclusive and exhaustive by construction, and their only job is the
reconciliation identity `sum(partitions) == 541,909`.

| Partition | Condition | Rows |
|---|---|---|
| P01_CANCELLATION_NEGATIVE | `C` prefix and `Quantity < 0` | 9,288 |
| P02_CANCELLATION_NON_NEGATIVE | `C` prefix and `Quantity >= 0` | 0 |
| P03_NEGATIVE_QUANTITY_NON_CANCEL | not `C`, `Quantity < 0` | 1,336 |
| P04_ZERO_QUANTITY | `Quantity == 0` | 0 |
| P05_POSITIVE_QUANTITY_ZERO_PRICE | not `C`, `Quantity > 0`, `UnitPrice == 0` | 1,179 |
| P06_POSITIVE_QUANTITY_NEGATIVE_PRICE | not `C`, `Quantity > 0`, `UnitPrice < 0` | 2 |
| P07_POSITIVE_QUANTITY_PAID | not `C`, `Quantity > 0`, `UnitPrice > 0` | 530,104 |
| P08_UNCLASSIFIABLE_MISSING_VALUES | `Quantity` or `UnitPrice` missing | 0 |
| **Total** | | **541,909** |

**Layer 2 — business classification** (`ProposedCategory`, 8 labels) is the
rule-based interpretation described in sections 5–6. Layer 2 may not be
inferred from Layer 1 alone: for example every P01 row is a cancellation, but
whether it is also a physical stock movement is unknowable from this dataset.

## 3. Category taxonomy

| Category | Meaning | Assigned when | Never assigned when |
|---|---|---|---|
| `CUSTOMER_SALE` | Ordinary merchandise sold to a customer | Non-`C` invoice, `Quantity > 0`, `UnitPrice > 0`, ordinary product code | Row is a non-product code, has a missing description pattern, or is on any `C` invoice |
| `CANCELLATION` | Row on a `C`-prefix invoice | `InvoiceNo` starts with `C` (project convention, holds for 100% of observed rows) | Row is on a numeric/`A` invoice |
| `SHIPPING_CHARGE` | Postage/carriage, not merchandise | StockCode `POST`, `DOT`, `C2` | Description contradicts the code (none observed) |
| `SERVICE_CHARGE` | Fee/commission, not merchandise | StockCode `BANK CHARGES`, `AMAZONFEE`, `CRUK` | — |
| `FINANCIAL_ADJUSTMENT` | Accounting entry with no product identity | Negative `UnitPrice`; StockCode `B` (bad debt); StockCode `D` (discount); supplier-credit note on a negative row | Row has a positive price and an ordinary product code |
| `PHYSICAL_STOCK_MOVEMENT` | Documented removal of goods from stock | Negative non-cancel row whose description states damage/disposal/unsaleable goods | Description does not state a physical event (then `UNKNOWN_PHYSICAL_IMPACT`) |
| `NEEDS_MANUAL_REVIEW` | Row is identifiable but its business event is not | Manual (`M`/`m`), samples (`S`), vouchers (`GIFT_*`), channel codes (`DCGS*`), `PADS`, stock-correction/ambiguous/other notes, zero-price rows with any description | Evidence fully determines the event |
| `UNKNOWN` | No usable evidence at all | Missing description on a negative non-cancel row, missing description on a zero-price row, missing `Quantity`/`UnitPrice` | Any row where evidence exists |

Observed distribution: `CUSTOMER_SALE` 527,725 · `CANCELLATION` 8,704 ·
`SHIPPING_CHARGE` 2,110 · `NEEDS_MANUAL_REVIEW` 1,581 · `UNKNOWN` 1,439 ·
`PHYSICAL_STOCK_MOVEMENT` 179 · `SERVICE_CHARGE` 87 ·
`FINANCIAL_ADJUSTMENT` 84.

### 3.1 Physical impact taxonomy (separate dimension)

| Value | Meaning | Rows |
|---|---|---|
| `PHYSICAL_STOCK_DECREASE` | Description or sale pattern evidences goods leaving stock | 527,904 |
| `NO_PHYSICAL_STOCK_MOVEMENT` | Financial/service entry only (postage, fees, discounts, bad debt) | 2,200 |
| `UNKNOWN_PHYSICAL_IMPACT` | Direction cannot be determined (all cancellations, all P03, all zero-price rows, manual/sample/voucher rows) | 11,805 |

`PHYSICAL_STOCK_INCREASE` exists in the code as a constant but is **never
assigned**: a cancellation or a negative row cannot be proven to re-enter
stock without a goods-receipt record this dataset does not contain.

### 3.2 Financial impact labels

`FinancialImpact` is derived from `ProposedCategory` × line value
(`Quantity * UnitPrice`, unrounded float64): `POSITIVE_VALUE`,
`NEGATIVE_VALUE`, `ZERO_VALUE`. It describes the recorded amount only; it is
not a claim about invoiced, paid or recoverable money.

## 4. Confidence model

| Level | Definition | Requirements | Rows |
|---|---|---|---|
| `HIGH` | Evidence is explicit, self-describing and uniform across every row of its class | Direct statement in the row (description, price sign, code identity) with zero observed contradicting rows | 10,760 |
| `MEDIUM` | Evidence is consistent and matches the project's established definitions, but one link is unverifiable from this dataset | Pattern-based (e.g. the V2 sale definition) with the missing link documented in `EvidenceContradicting` | 529,030 |
| `LOW` | Only circumstantial evidence; several business interpretations remain equally consistent | Short/ambiguous notes, voucher or channel ambiguity, zero-price with an ordinary description | 680 |
| `UNKNOWN` | No evidence to evaluate | Missing description or missing numeric value | 1,439 |

Every row carries `ConfidenceExplanation` (why this level) **and**
`EvidenceContradicting` (what would falsify or weaken it). Confidence is
never raised above the strongest *weakest* link: a rule with uniform
description evidence but no fulfilment record caps at `MEDIUM` for that
reason (`PAID_NON_CANCEL`).

`ManualReviewRequired = YES` (3,025 rows) is set whenever the classification
identifies the *type* of entry but not its *business event*.

## 5. Evidence rules — ordered, first match wins

Rules are evaluated in the exact order below. Specific, self-describing
evidence is placed before generic structural rules; negative-quantity
evidence is placed before zero-price evidence. The first rule whose condition
holds claims the row; later rules cannot override it.

| # | Rule | Condition (plain English) | Category | Conf. | Physical | Manual | Rows |
|---|---|---|---|---|---|---|---|
| 1 | `NEGATIVE_UNIT_PRICE` | `UnitPrice < 0` | FINANCIAL_ADJUSTMENT | HIGH | NONE | NO | 2 |
| 2 | `BAD_DEBT_STOCKCODE` | StockCode `B` | FINANCIAL_ADJUSTMENT | HIGH | NONE | YES | 1 |
| 3 | `POSTAGE_CODE` | StockCode `POST`/`DOT` | SHIPPING_CHARGE | HIGH | NONE | NO | 1,966 |
| 4 | `CARRIAGE_CODE` | StockCode `C2` | SHIPPING_CHARGE | MEDIUM | NONE | NO | 144 |
| 5 | `FEE_AND_COMMISSION_CODES` | StockCode `BANK CHARGES`/`AMAZONFEE`/`CRUK` | SERVICE_CHARGE | HIGH | NONE | NO | 87 |
| 6 | `DISCOUNT_CODE` | StockCode `D` | FINANCIAL_ADJUSTMENT | MEDIUM | UNKNOWN | NO | 77 |
| 7 | `MANUAL_CODE` | StockCode `M`/`m` | NEEDS_MANUAL_REVIEW | MEDIUM | UNKNOWN | YES | 572 |
| 8 | `SAMPLES_CODE` | StockCode `S` | NEEDS_MANUAL_REVIEW | MEDIUM | UNKNOWN | YES | 63 |
| 9 | `PADS_CODE` | StockCode `PADS` | NEEDS_MANUAL_REVIEW | MEDIUM | UNKNOWN | YES | 4 |
| 10 | `GIFT_VOUCHER_CODES` | StockCode starts `GIFT_` | NEEDS_MANUAL_REVIEW | LOW | UNKNOWN | YES | 34 |
| 11 | `DCGS_CODES` | StockCode starts `DCGS` | NEEDS_MANUAL_REVIEW | LOW | UNKNOWN | YES | 45 |
| 12 | `MISSING_NUMERIC_VALUES` | `Quantity` or `UnitPrice` missing | UNKNOWN | UNKNOWN | UNKNOWN | YES | 0 |
| 13 | `ZERO_QUANTITY` | `Quantity == 0` | INVALID_RECORD | MEDIUM | NONE | YES | 0 |
| 14 | `CANCELLATION_NEGATIVE` | `C` prefix and `Quantity < 0` | CANCELLATION | HIGH | UNKNOWN | NO | 8,704 |
| 15 | `CANCELLATION_NON_NEGATIVE` | `C` prefix and `Quantity >= 0` | CANCELLATION | MEDIUM | UNKNOWN | YES | 0 |
| 16 | `NEGATIVE_NON_CANCEL_MISSING_DESCRIPTION` | P03 row, no description | UNKNOWN | UNKNOWN | UNKNOWN | YES | 855 |
| 17 | `NEGATIVE_NON_CANCEL_SUPPLIER_CREDIT` | P03 row, credit/ASOS/supplier note | FINANCIAL_ADJUSTMENT | LOW | UNKNOWN | YES | 4 |
| 18 | `NEGATIVE_NON_CANCEL_WRITE_OFF` | P03 row, damage or disposal note | PHYSICAL_STOCK_MOVEMENT | MEDIUM | DECREASE | NO | 179 |
| 19 | `NEGATIVE_NON_CANCEL_STOCK_CORRECTION` | P03 row, record-correction note | NEEDS_MANUAL_REVIEW | MEDIUM | UNKNOWN | YES | 135 |
| 20 | `NEGATIVE_NON_CANCEL_AMBIGUOUS_NOTE` | P03 row, short ambiguous note | NEEDS_MANUAL_REVIEW | LOW | UNKNOWN | YES | 98 |
| 21 | `NEGATIVE_NON_CANCEL_OTHER_NOTE` | P03 row, any other note | NEEDS_MANUAL_REVIEW | LOW | UNKNOWN | YES | 53 |
| 22 | `ZERO_PRICE_MISSING_DESCRIPTION` | P05 row, no description | UNKNOWN | UNKNOWN | UNKNOWN | YES | 584 |
| 23 | `ZERO_PRICE_ADMIN_NOTE` | P05 row, admin/correction note | NEEDS_MANUAL_REVIEW | MEDIUM | UNKNOWN | YES | 131 |
| 24 | `ZERO_PRICE_PRODUCT_DESCRIPTION` | P05 row, any other description | NEEDS_MANUAL_REVIEW | LOW | UNKNOWN | YES | 446 |
| 25 | `PAID_NON_CANCEL` | not `C`, `Quantity > 0`, `UnitPrice > 0` | CUSTOMER_SALE | MEDIUM | DECREASE | NO | 527,725 |

**Total assigned: 541,909 (0 unmatched).**

### 5.1 Why this order

- **Specific codes (3–11) before cancellation (14–15).** A `D` row on a `C`
  invoice is explained more precisely by its code (discount) than by the
  invoice prefix alone. 584 cancellation-invoice rows carry special codes;
  classifying them only as cancellations would discard their code evidence.
- **Structural checks (12–13) before interpretation rules.** Missing/zero
  quantities are decided on the numbers, not on descriptions.
- **Negative quantity (16–21) before zero price (22–24).** 1,336 P03 rows are
  priced at 0.00. Their negative-quantity evidence is decisive; a zero-price
  rule would relabel a write-off as an unpriced sale-like row.
- **Paid rule last (25).** It is the most generic pattern, so every specific
  exception must have been rejected first.

### 5.2 Description buckets (evidence extraction, rules 16–24)

Negative non-cancel rows (`NEGATIVE_BUCKETS`, first match):
`MISSING_DESCRIPTION` → `SUPPLIER_CREDIT` (`credit|asos|supplier`) →
`DAMAGE_OR_DEFECT` (`damag|broken|faulty|mould|mold|rusty|smudg|smashed|crushed|wet pallet`)
→ `DISPOSAL_OR_DESTROYED` (`throw away|thrown away|destroyed|unsaleable|unsalable|can't sell|cannot sell`)
→ `STOCK_OR_ENTRY_CORRECTION` (`incorrect stock|wrongly marked|wrongly coded|came coded|wrong code|check`)
→ `AMBIGUOUS_SHORT_NOTE` (`^\?+$|missing|found|ebay|dotcom|sold as set|manual`)
→ default `OTHER_EXPLICIT_NOTE`.

Zero-price rows (`ZERO_PRICE_BUCKETS`): `MISSING_DESCRIPTION` →
`ADMINISTRATIVE_OR_CORRECTION_NOTE` (`check|found|adjust|credit|coded|wrong|incorrect|manual|missing|amazon|ebay|^\?+$`)
→ default `ORDINARY_PRODUCT_DESCRIPTION`.

**Precedence invariant:** zero-price buckets only fill rows that no negative
bucket claimed. A row that is both negative-quantity and zero-price keeps its
negative bucket. (Regression-tested by `BucketPrecedenceTests`; this
invariant was violated by an earlier draft, leaving 469 rows unclassified.)

## 6. Evidence standards

Each register entry separates three text fields:

| Field | Content rule |
|---|---|
| `ObservedCharacteristics` | Machine-computed facts about the row only (quantity, price, prefix, code, description text, flags). No interpretation. |
| `EvidenceSupporting` | What in the row or in the whole-dataset pattern supports the assigned category. |
| `EvidenceContradicting` | What is missing or contradictory — the strongest reason the confidence is not higher. |

Accepted evidence strengths, strongest first:

1. **Row-intrinsic fact** — value, sign, code, prefix, exact description text.
2. **Whole-dataset uniformity** — e.g. “every one of the 1,256 `POST` rows
   says `POSTAGE`” (basis for `HIGH`).
3. **Project definition match** — e.g. the V2 sale definition (basis for
   `MEDIUM`, never `HIGH`, because fulfilment is unrecorded).
4. **Absence of evidence** — only ever supports `UNKNOWN`/`LOW`, never a
   positive claim.

Explicitly *not* accepted: external assumptions about the business, name-based
guesses for codes not measured, and inference from quantity sign alone.

## 7. Traceability standards

- `SourceRow` = Excel row number (header occupies row 1; data rows are
  `2..541910`, contiguous, verified).
- Register scope `ROW`: every row outside P07, every non-standard StockCode,
  and every `|Quantity| >= 1000` row (14,682 entries, one per source row).
- Register scope `GROUP`: the remaining ordinary paid rows, aggregated in 2
  entries (527,227 rows) with no per-row claim attached.
- Identity: `sum(RowCount) == 541,909`; `ROW` entries have unique
  `SourceRow`; no source row appears in two entries.

## 8. Reproducibility standards

- Fixed rule order, fixed iteration order, no timestamps in any output →
  repeated runs of the audit script produce byte-identical files (verified by
  SHA-256 over all seven outputs: two consecutive runs matched before the
  final wording fixes, and two further consecutive runs matched after them).
- Money is computed as unrounded float64 `Quantity * UnitPrice`; 2-decimal
  formatting is display-only; V2 comparisons use the project's existing 0.01
  tolerance.
- Protected files are fingerprinted before and after each run; the audit
  aborts if any SHA-256 changes.
- Tests: `python -m unittest discover -s tests` (41 tests, all passing;
  full-dataset subset behind `TREXO_SLOW_TESTS=1`).

## 9. Divergences from `classify_transaction_types.py`

The earlier script remains untouched and its outputs remain valid as a
*structural* summary. This policy deliberately differs in the following ways:

| # | Earlier pattern | This policy | Why |
|---|---|---|---|
| 1 | Output printed to console only | Row-level CSV register with `SourceRow`, evidence, confidence, status | Auditability and traceability were required |
| 2 | 6 structural types (`CANCELLATION_NEGATIVE`, `CANCELLATION_POSITIVE`, `NON_CANCELLATION_NEGATIVE`, `POSITIVE_ZERO_PRICE`, `POSITIVE_PAID_SALE`, `OTHER_OR_INVALID`) | 8 business categories + 4-way confidence + 3-way physical impact | Structural type ≠ business meaning (a `POST` row is structurally a paid sale but is not merchandise) |
| 3 | Non-product codes (`POST`, `DOT`, `M`, `C2`, `S`, `D`, `PADS`, …) fall inside `POSITIVE_PAID_SALE` / `NON_CANCELLATION_NEGATIVE` | Separated into SHIPPING / SERVICE / FINANCIAL / NEEDS_MANUAL_REVIEW | 2,379 paid rows and all fee/discount rows would otherwise be counted as merchandise sales |
| 4 | Negative non-cancel description patterns: damage → disposal → correction → credit → `OTHER_EXPLICIT_NOTE` (`.+`), default `MISSING_OR_UNCLASSIFIED` | Adds explicit `MISSING_DESCRIPTION` (first) and `AMBIGUOUS_SHORT_NOTE` buckets; reorders `SUPPLIER_CREDIT` **before** damage; adds `smashed|crushed|wet pallet` and `can't sell|cannot sell` | 862 of 1,336 P03 rows have no description: they are now an explicit UNKNOWN rule (16) instead of a print-only `MISSING_OR_UNCLASSIFIED` bucket, and short notes such as `?` / `found` / `ebay` are separated from substantive notes rather than merged into `OTHER_EXPLICIT_NOTE`; a note such as *“damages/credits from ASOS”* is supplier-credit evidence and must not be promoted to a physical write-off |
| 5 | `CREDIT_OR_SUPPLIER_ADJUSTMENT` (same pattern, later position) | `SUPPLIER_CREDIT` earlier in the order | Same as #4 — ordering is an evidence decision and is documented, not silent |
| 6 | `OTHER_OR_INVALID` for the 2 bad-debt rows | `NEGATIVE_UNIT_PRICE` / `BAD_DEBT_STOCKCODE` → `FINANCIAL_ADJUSTMENT` HIGH | The rows are self-describing accounting entries; and the positive twin (A563185) is reported as CRITICAL anomaly ANOM-0001 |
| 7 | No physical-impact dimension | `PhysicalInventoryImpact` on every row; stock increase never asserted | Financial and physical effects must not be mixed |
| 8 | No confidence or manual-review flag | 4 confidence levels, `ManualReviewRequired`, `ConfidenceExplanation`, `EvidenceContradicting` | Reviewers must see *why* and *how weak* |
| 9 | Zero-price rows reported as a count only | Bucket-based sub-classification into UNKNOWN / NEEDS_MANUAL_REVIEW; never `CUSTOMER_SALE` | Zero price cannot be an ordinary sale under governance rule 6 |
| 10 | No source-row identifiers | `SourceRow` on every entry | Lineage requirement |

**Unchanged on purpose:** the sale definition
(`not C AND Quantity > 0 AND UnitPrice > 0`), the `C`-prefix cancellation
convention, revenue = `Quantity * UnitPrice`, invoice count = `nunique`, and
the 0.01 reconciliation tolerance. The V2 reconciliation re-run confirms 0
mismatches under these definitions.

## 10. What this policy explicitly does NOT decide

These are approval-gate items; the audit reports them but takes no action:

1. Whether bad-debt row A563185 (+11,062.06) must be excluded from V2 sales
   and product movement (ANOM-0001, CRITICAL).
2. Whether non-product codes belong in a product-movement dataset at all
   (ANOM-0004…0007; V3 does not exist and must not be created without
   approval).
3. How cancellations are separated from returns, and whether any cancellation
   may ever count as a stock increase.
4. Treatment of the 5,268 exact duplicate rows.
5. Whether zero-price rows may ever count as sales, and on what evidence.
6. The canonical StockCode normalisation rule (`15056BL`/`15056bl`, `M`/`m`).
7. Which `NEEDS_MANUAL_REVIEW` / `UNKNOWN` groups may be resolved, and on
   what evidence.

## 11. Change control

- Any rule edit = policy version bump (`V1` → `V2`), script re-run, full
  re-reconciliation, and a diff of the register (rows whose category,
  confidence or physical impact changed), submitted for approval.
- Rule conditions live in exactly one place (`_rules()` in
  `src/trexo/audit_special_transactions.py`); this document mirrors them and
  must be updated in the same change.
- Anomalies are never auto-resolved by a classification change; resolution
  status changes only through explicit review.

## 12. Approval request

Approval of this policy would authorise, in order:
(a) using these categories as the canonical row-level classification for
downstream analytics; (b) deciding the seven items in section 10; only then
(c) considering whether a revised product-movement dataset is warranted.
No V3 dataset, forecast, or model may be built before (a)–(c) are answered.

---

*Generated as part of Special Transaction Audit V1. Facts in this document
are measured from the source dataset; interpretations are labelled as
proposals.*
