# TREXO-INDIA — Approved Data Foundation Design V1

| Field | Value |
|---|---|
| **Document title** | TREXO-INDIA Approved Data Foundation Design |
| **Document ID** | `TREXO-DATA-FOUNDATION-DESIGN-V1` |
| **Version** | V1 (first design issue) |
| **Status** | `BLOCKED_BY_OWNER` — **no data foundation is approved** |
| **Scope** | Logical design of the twelve data layers that would constitute the TREXO data foundation after owner approval. Design only. |
| **Repository** | `E:\TREXO-INDIA` |
| **Supersedes** | Nothing |
| **Date of issue** | 2026-11-19 |
| **Authority** | The project owner. This document is decision support, not a decision. |

> **Status statement (binding).** The word "Approved" in this filename is a mandate
> artefact, not a status. **No data foundation is approved.** What follows is a design
> for the foundation that *would* exist after the owner has answered D01–D07. Every
> layer marked `BLOCKED` is blocked, not pending implementation. Every decision in this
> document is `PENDING`.
>
> **This document contains no implementation.** It creates no pipeline, no schema, no
> database, no configuration and no code. It describes intent, grain, contracts and
> gates only.

---

## 1. Purpose and reading guide

### 1.1 Why this document exists

The Special Transaction Audit V1 measured the transaction dataset thoroughly but left
every business rule unresolved. A future foundation must therefore be designed in a way
that (a) can be built incrementally from what already exists, (b) cannot silently absorb
an unapproved rule, and (c) keeps financial and physical facts apart at every layer. This
document defines that foundation as twelve explicit layers with hard boundaries.

### 1.2 What is fixed and what is open

| Class | Position |
|---|---|
| Source facts | Fixed: 541,909 rows, 25,900 invoices, 4,070 raw StockCodes, 2010-12-01 → 2011-12-09 |
| V2 sale definition | Fixed as an existing artefact, **not** approved as a governance rule |
| Audit partitions P01–P08 | Fixed measurements; exhaustiveness verified |
| Classification register | A proposal; 93 anomalies remain `OPEN`; nothing promoted |
| D01–D07 | `PENDING`; no layer that depends on them may be built |
| Inventory, cost, receipt, PO, supplier, warehouse, returns data | **Absent**; blocks five layers outright |

### 1.3 Reading convention

Each layer is described by seven attributes: **purpose**, **grain**, **key fields**,
**source**, **immutability** (immutable fact vs derived artefact), **owner-approval
dependency**, and **must not contain**. The last attribute is a prohibition, not a
preference; it is the mechanism by which layers stay separated.

---

## 2. Non-negotiable separation rules

These five rules bind every layer below. A design that violates any of them is invalid
regardless of how convenient it is.

| # | Rule | Consequence if broken |
|---|---|---|
| S1 | **Financial and physical impact never share a field.** A row may be a financial adjustment with no stock effect, a stock movement with no revenue, both, or neither. | The bad-debt event (D01, net −£11,062.06) becomes indistinguishable from a sale, and cancellation sign is read as stock direction (D03). |
| S2 | **Classification and measurement are separate partitions.** Measurement (P01–P08) is arithmetic over `InvoiceNo`, `Quantity`, `UnitPrice`; classification is an evidence-based interpretation. | A measurement label gets treated as a business fact, or a business label is used to justify an arithmetic total. |
| S3 | **The raw source is never overwritten.** It is read once, hashed, and copied into staging with a preserved row reference. | Reconciliation to 541,909 rows becomes impossible and no figure can be defended. |
| S4 | **Every derived row preserves its source row reference.** No aggregate, metric or score is admissible without a path back to `SourceRow`. | A number in a report cannot be explained, audited or corrected. |
| S5 | **Uncertainty survives.** `UNKNOWN` and `NEEDS_MANUAL_REVIEW` are durable states that propagate into downstream layers and confidence displays. | 3,025 manual-review rows are silently forced into the nearest category, manufacturing false certainty. |

**Corollary.** Because S1 forbids a combined field, no layer may carry a column such as
`net_effect` that adds revenue and stock quantity together. Where a combined view is
needed for reporting it is produced at the presentation layer from two separate columns,
never stored as a fact.

---

## 3. The twelve layers

The layers are numbered L01–L12 in dependency order. L01–L03 can be designed and built
now. L04–L05 are design-complete but blocked by D02–D07. L06 is blocked by D01/D03/D05.
L07–L09 are blocked by absent external data. L10 depends on L04–L06. L11 is blocked by
L07–L10. L12 is buildable now and must run alongside every other layer.

### 3.1 L01 — Raw source layer

| Attribute | Design |
|---|---|
| **Purpose** | Hold the unmodified source exactly as received, with provenance, so that every later layer can be proved to derive from it. |
| **Grain** | One immutable file per source delivery; for the transaction workbook, one physical row per spreadsheet row (header excluded). |
| **Key fields** | `source_id`, `source_file_name`, `source_sha256`, `received_at`, `row_count`, `column_count`, `licence_reference`. Row content is *not* keyed here beyond physical position. |
| **Source** | `data/raw/Online Retail.xlsx` (SHA-256 `43465A06…4676D` recorded in the Approval Review Pack). |
| **Immutability** | **Immutable.** Read-only. Never edited, never re-saved, never normalised in place. |
| **Owner-approval dependency** | None for retention. Any *replacement* of the source requires owner approval and a new `source_id`. |
| **Must NOT contain** | Cleaning, casts, trims, deduplication, category labels, currency conversion, derived dates, "corrected" values. |

The raw layer's only job is to be a defensible origin. If a downstream layer is ever
doubted, the raw layer is the arbiter.

### 3.2 L02 — Source staging layer

| Attribute | Design |
|---|---|
| **Purpose** | Make the raw file queryable without changing it: typed columns, a contiguous `SourceRow`, and a manifest of the load. |
| **Grain** | One row per source row, `SourceRow` = Excel row number (header = row 1; data = 2…541,910). |
| **Key fields** | `SourceRow` (unique, contiguous), `InvoiceNo`, `StockCode` **as text**, `StockCodeRawType`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`, `LineValue`, `LoadBatchId`. |
| **Source** | L01. |
| **Immutability** | **Derived but append-only.** One staging batch per source version; existing batches are never re-written. |
| **Owner-approval dependency** | None. This layer applies no judgement: it casts types, adds the row index and computes `Quantity × UnitPrice`. |
| **Must NOT contain** | Case-folded or merged codes, category labels, duplicate flags used as filters, deletion of any row, imputation of missing `CustomerID` or `Description`. |

**Hard typing rule.** `StockCode` must be cast to text *before* any pattern check. The
dataset contains 487,036 integer-typed and 54,873 string-typed values on raw read; a
pattern test applied before the cast silently ignores 487,036 rows. The staging layer
records the observed raw type per row (`StockCodeRawType`) so that this failure mode is
provable, not assumed.

### 3.3 L03 — Validated transaction layer

| Attribute | Design |
|---|---|
| **Purpose** | Certify that each staged row is structurally admissible (types, ranges, referential shape), and publish a data-quality state per row and per batch. |
| **Grain** | One row per staged row that passes structural validation; failures go to quarantine (L12), never to deletion. |
| **Key fields** | `SourceRow`, `ValidationBatchId`, `ValidationStatus` (`PASS`, `PASS_WITH_WARNING`, `QUARANTINED`), `ValidationRuleSetVersion`, `WarningCodes[]`, `MeasuredPartition` (P01–P08), `LineValue`. |
| **Source** | L02 + validation specification (`TREXO_DATA_VALIDATION_SPECIFICATION_V1`). |
| **Immutability** | **Derived, versioned.** A new validation rule set produces a new batch; the previous batch is retained. |
| **Owner-approval dependency** | Structural checks: none. Any check whose threshold encodes a business rule (for example whether a zero price is admissible as a sale) is **blocked by D05**. |
| **Must NOT contain** | Business categories, confidence about business meaning, deduplication decisions, exclusion of D01–D07 populations from the row set. |

The measured partition (P01–P08) is arithmetic, not interpretation. It exists here so
that the reconciliation identity `Σ partitions = 541,909` can be tested at the earliest
possible layer. The layer must still carry the manual-review population — 1,439
`UNKNOWN` plus 1,581 `NEEDS_MANUAL_REVIEW`, with the `ManualReviewRequired` flag
totalling 3,025 rows — as a *warning*, not a filter.

### 3.4 L04 — Product identity layer

| Attribute | Design |
|---|---|
| **Purpose** | Resolve a raw `StockCode` string into a governed product identity, keeping the original permanently and making every merge reversible. |
| **Grain** | Two grains: `product_identity` (one row per canonical product) and `product_alias` (one row per raw code variant mapped to a canonical product). |
| **Key fields** | `CanonicalProductCode`, `OriginalStockCode`, `AliasType` (`EXACT`, `CASE_FOLD`, `EVIDENCE_MERGE`), `EvidenceReference`, `MergeDecisionId`, `ValidFrom`, `ValidTo`, `IsReversible`, `ProductClass`. |
| **Source** | L03 `StockCode` + owner-approved code registry (D02) + identity decisions (D06). |
| **Immutability** | **Derived and append-only.** A merge is closed by an end date, never edited away. |
| **Owner-approval dependency** | **Blocked by D02 and D06.** No canonical code may be created, and no variant merged, before the owner approves the rule. Measured scope: 4,070 raw codes; 487,036 int-typed + 54,873 str-typed values; 112 case collisions. |
| **Must NOT contain** | Destruction of the original code, silent merges, inferred product descriptions used as identity evidence, category assignments used to justify a merge. |

### 3.5 L05 — Transaction classification layer

| Attribute | Design |
|---|---|
| **Purpose** | Attach, per row and per governed group, the proposed business event, the financial impact dimension, the physical impact dimension, confidence and manual-review state. |
| **Grain** | `transaction_classification`: one row per source row for the ROW scope; `transaction_classification_group`: one row per governed group with `RowCount`. Coverage identity: 14,682 ROW entries + 2 GROUP entries covering 527,227 rows = 541,909 rows. |
| **Key fields** | `ClassificationId`, `SourceRow` (nullable only for GROUP scope), `ClassificationScope` (`ROW`/`GROUP`), `RowCount`, `ProposedCategory`, `FinancialImpact`, `PhysicalImpact`, `ConfidenceLevel`, `EvidenceSupporting`, `EvidenceContradicting`, `ManualReviewRequired`, `RuleId`, `RuleSetVersion`. |
| **Source** | L03 + `docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md`. |
| **Immutability** | **Derived, versioned.** Rules are proposed; a rule change creates a new rule-set version and a full register diff. |
| **Owner-approval dependency** | **Blocked by D03, D05, D07.** The taxonomy may be stored as a proposal now; it may not be treated as canonical until approved. |
| **Must NOT contain** | A single field carrying both financial and physical meaning, auto-resolution of anomalies, promotion of `PROPOSED_*` status to `APPROVED`, deletion of `UNKNOWN` rows. |

### 3.6 L06 — Financial adjustment layer

| Attribute | Design |
|---|---|
| **Purpose** | Preserve accounting events (bad debt, fee, discount, credit, service charge) as financial facts that are visible to finance and excluded from product-sales analytics. |
| **Grain** | One row per source row carrying a financial-adjustment classification, plus a group identifier for multi-leg events. |
| **Key fields** | `AdjustmentId`, `AdjustmentGroupId`, `SourceRow`, `EventType`, `SignedAmount`, `Currency`, `EvidenceReference`, `GroupNetAmount`, `ApprovalReference`. |
| **Source** | L05 rows where `ProposedCategory = FINANCIAL_ADJUSTMENT`, plus the D01 group. |
| **Immutability** | **Derived, append-only.** An adjustment is never netted to zero by editing; a correcting entry is a new row. |
| **Owner-approval dependency** | **Blocked by D01.** Measured scope: 3 rows on invoices A563185–A563187, group net **−£11,062.06**; the positive leg currently counts as £11,062.06 of V2 product sales. |
| **Must NOT contain** | Quantities interpreted as stock movement, product descriptions, product-movement labels, silent netting of the two credit legs against the debit leg. |

The financial-adjustment layer exists so that the reconciliation identity
`product revenue + financial adjustments = total accounting revenue` can be stated and
tested. It does not assert that the accounting treatment is correct; the ledger that
would prove that is external and absent.

### 3.7 L07 — Physical movement layer

| Attribute | Design |
|---|---|
| **Purpose** | Record what is *evidenced* about goods entering or leaving stock, independent of any revenue value. |
| **Grain** | One row per source row that has a physical-movement classification, plus (when available) one row per goods receipt. |
| **Key fields** | `MovementId`, `SourceRow`, `MovementDirection` (`DECREASE`, `INCREASE`, `NONE`, `UNKNOWN`), `EvidenceType`, `ProductIdentityKey`, `MovementDate`, `MovementQuantity`, `EvidenceStrength`. |
| **Source** | L05 `PhysicalImpact` dimension; future goods-receipt ledger. |
| **Immutability** | **Derived, versioned.** Direction upgrades (for example `UNKNOWN` → `INCREASE` when a receipt is found) are new versions with evidence. |
| **Owner-approval dependency** | **Blocked by D03 and D05.** The dataset does not link a `C` invoice to a stock receipt; 1,336 zero-price negative rows suggest write-offs but do not prove direction. |
| **Must NOT contain** | Revenue, unit price as a proxy for cost, `PHYSICAL_STOCK_INCREASE` inferred from a negative sign, cancellation rows asserted as stock returns. |

**Prohibition.** `PHYSICAL_STOCK_INCREASE` may only be populated from a goods-receipt
record. No sales-side inference is admissible, because the dataset has no returns data,
no warehouse data and no stock ledger.

### 3.8 L08 — Inventory snapshot layer

| Attribute | Design |
|---|---|
| **Purpose** | Hold point-in-time stock positions per product, warehouse and date, once such data exists. |
| **Grain** | One row per (`SnapshotDate`, `ProductIdentityKey`, `WarehouseId`). |
| **Key fields** | `SnapshotId`, `SnapshotDate`, `ProductIdentityKey`, `WarehouseId`, `OnHandQty`, `ReservedQty`, `AverageCost`, `Currency`, `SourceSystem`, `SourceRecordHash`. |
| **Source** | External inventory system (**absent**). |
| **Immutability** | **Immutable fact.** Snapshots are append-only; a corrected snapshot is a new dated row. |
| **Owner-approval dependency** | **Blocked by external data.** No snapshot exists in the repository. |
| **Must NOT contain** | Stock inferred from sales, negative on-hand, cost back-filled from selling price, valuation without a declared cost method. |

**Standing prohibition.** The absence of this layer is the single hard reason that
"actual dead stock" cannot be computed today. No layer above it may simulate a snapshot.

### 3.9 L09 — Goods receipt layer

| Attribute | Design |
|---|---|
| **Purpose** | Record dated receipts of goods, enabling unit age, FIFO layering, receipt-based product age and supplier-return windows. |
| **Grain** | One row per (`ReceiptDate`, `ProductIdentityKey`, `WarehouseId`, `PurchaseOrderId`, `ReceiptLine`). |
| **Key fields** | `ReceiptId`, `ReceiptDate`, `ProductIdentityKey`, `WarehouseId`, `QuantityReceived`, `UnitCost`, `SupplierId`, `PurchaseOrderId`, `SourceSystem`. |
| **Source** | External goods-in ledger and purchase-order system (**absent**). |
| **Immutability** | **Immutable fact.** |
| **Owner-approval dependency** | **Blocked by external data.** |
| **Must NOT contain** | Inferred receipt dates from first-sale dates, cost derived from selling price, aggregated receipts that lose lot identity. |

### 3.10 L10 — Product demand layer

| Attribute | Design |
|---|---|
| **Purpose** | Convert admissible transaction rows into per-product demand measures at a declared grain and window, with every measure carrying its window and rule version. |
| **Grain** | `product_demand_period`: one row per (`ProductIdentityKey`, `PeriodStart`, `PeriodType`). `product_demand_summary`: one row per product with declared windows. |
| **Key fields** | `ProductIdentityKey`, `PeriodStart`, `PeriodEnd`, `WindowDays`, `UnitsSold`, `InvoiceCount`, `LineCount`, `FirstSaleDate`, `LastSaleDate`, `RecencyDays`, `DemandCv`, `SourceRowRange`, `RuleSetVersion`, `ThresholdSetVersion`, `DataQualityFlag`. |
| **Source** | L03 + L04 + L05 + `data/processed/product_monthly_sales_v2.csv` as an existing derived artefact. |
| **Immutability** | **Derived, versioned.** Recomputation is idempotent and produces a new dataset version, never an in-place edit. |
| **Owner-approval dependency** | **Partially blocked.** The measurement is computable now; which rows are admissible (D02, D03, D04, D05) and which identity key is canonical (D06) are `PENDING`. |
| **Must NOT contain** | Inventory quantities, cost, "dead" labels, profitability, any claim about current stock, product populations that include service, shipping or financial codes. |

The published baseline — 3,898 products, 460 with no sale in the final 180 days,
£103,128.42 of historical line value — belongs to this layer and is explicitly a
*sales-side, historical* measurement. It is not a stock statement.

### 3.11 L11 — Dead-stock intelligence layer

| Attribute | Design |
|---|---|
| **Purpose** | Produce detection registers, risk scores and recommendations from L08–L10 evidence, with capability-level truthfulness about what can and cannot be computed. |
| **Grain** | `detection_register`: one row per (`ProductIdentityKey`, `DetectionType`, `Window`, `ThresholdId`). `risk_score`: one row per (`ProductIdentityKey`, `ScoreFamily`, `ScoreVersion`). |
| **Key fields** | `DetectionType` (`HISTORICALLY_NON_MOVING`, `SLOW_MOVING`, `EXCESS`, `AGED`, `DEAD_CANDIDATE`), `WindowDays`, `ThresholdId`, `Indicators[]`, `AvailableMask`, `ConfidenceLabel`, `LimitationText`, `ScoreFamily` (A/B/C/D), `RequiresInputs[]`, `ApprovalReference`. |
| **Source** | L10 metrics; L08/L09 when available; threshold registry (policy-controlled). |
| **Immutability** | **Derived, versioned.** Every output stores its input versions and threshold version. |
| **Owner-approval dependency** | **Blocked.** Family A requires approved thresholds; families B and D require L08 and cost; family C requires approved modelling, which is out of scope. |
| **Must NOT contain** | `DEAD_CANDIDATE` without on-hand evidence, financial exposure without acquisition cost, a score without its available-mask and limitations, a recommendation with `approved_by` set. |

### 3.12 L12 — Data-quality and audit layer

| Attribute | Design |
|---|---|
| **Purpose** | Record every anomaly, validation failure, quarantine decision, rule change and approval as immutable audit history, and expose the current quality state to every consumer. |
| **Grain** | `anomaly`: one row per anomaly occurrence; `audit_event`: one row per state change; `dataset_manifest`: one row per derived dataset version. |
| **Key fields** | `AnomalyId`, `Severity`, `Status` (`OPEN`/`CLOSED`), `AffectedSourceRows[]`, `AuditEventId`, `Actor`, `EventType`, `BeforeState`, `AfterState`, `DatasetId`, `ReportHash`, `ApprovalReference`. |
| **Source** | All layers; existing `reports/special_transaction_anomalies_v1.csv` (93 open). |
| **Immutability** | **Immutable, append-only.** No audit event is edited or deleted; corrections are new events. |
| **Owner-approval dependency** | None to record. Closing an anomaly requires human review; resolving a business question requires owner approval. |
| **Must NOT contain** | Deletion of anomaly history, automatic closure of anomalies, mutable status fields without a corresponding event, personal data beyond what the source already holds. |

---

## 4. Product identity design

### 4.1 The six identity attributes

| Attribute | Purpose | Rule |
|---|---|---|
| `OriginalStockCode` | The exact string observed in the source, preserved verbatim. | Never altered, never upper-cased in place. |
| `CanonicalProductCode` | The governed identifier used by analytics. | Created only under an approved identity rule. |
| `AliasType` | How a variant relates to the canonical code. | One of `EXACT`, `CASE_FOLD`, `EVIDENCE_MERGE`. |
| `DescriptionHistory` | Every distinct description observed for the identity, with dates. | Append-only; a changed description is history, not a correction. |
| `ProductCategory` / `ProductClass` | Business class (physical product, shipping, service, financial, promotional, administrative, unknown). | `UNKNOWN` by default; never guessed. |
| `LifecycleStatusAndUoM` | Active/discontinued/unknown, and unit of measure. | `UNKNOWN` unless an external master supplies it; UoM is not inferable from `Quantity`. |

### 4.2 Warehouse attribute

Warehouse is **not** derivable. It appears in the identity design only as a reserved
field that must be supplied by L08. Until then it is declared absent, and no
per-warehouse identity, transfer or location-level ageing claim may be made.

### 4.3 Reversibility and evidence

1. Every merge stores the original code, the decision identifier and the evidence
   reference; un-merging is a data operation over `product_alias`, not a rewrite.
2. A merge requires evidence of the same physical product: a description match, a
   supplier master entry, or an owner decision. Code similarity alone is not evidence.
3. No merge may be justified by a classification label, because classification is
   itself `PENDING`.
4. The measured case-collision scope is 112 collisions across 4,070 raw codes. Merging
   them changes the product count from 4,070 raw codes to a smaller canonical set; that
   count change must be published with the decision, not absorbed silently.

### 4.4 The 15056BL test

`15056BL` is a real physical product (description "EDWARDIAN PARASOL BLACK") worth
**£16,915.72** in V2 line value, and it appears as two raw variants. A blanket
non-standard-code exclusion leaves 3,898 code rows from 3,922 and deletes this product.
The identity design therefore treats blanket exclusion as an invalid rule, not a
conservative default. The correct population is 3,898 code rows *plus* the retained
`15056BL` family, subject to owner approval under D02/D06.

---

## 5. The gating model

### 5.1 Buildable now (design and construction)

| Layer | Why it can proceed | Constraint |
|---|---|---|
| L01 Raw source | File exists, hashed, immutable | None beyond retention |
| L02 Source staging | Pure typing and indexing | Must preserve `StockCodeRawType` |
| L03 Validated transaction | P01–P08 are arithmetic | Business-rule checks withheld |
| L12 Data-quality and audit | Recording is not deciding | Anomalies stay `OPEN` |

### 5.2 Blocked by a governance decision

| Layer | Blocking decisions | Measured scope |
|---|---|---|
| L04 Product identity | D02, D06 | 24 non-standard codes in V2; 112 case collisions |
| L05 Transaction classification | D03, D05, D07 | 9,288 cancellations; 2,515 zero-price rows; 3,025 manual-review rows |
| L06 Financial adjustment | D01 | 3 rows, net −£11,062.06 |
| L07 Physical movement | D03, D05 | 1,336 zero-price negative rows with no proven direction |
| L10 Product demand (admissibility) | D02, D04 | 2,762 V2 rows / £412,565.65 on non-standard codes; 5,268 duplicate extra rows |
| L11 Dead-stock intelligence | All of D01–D07 for thresholds and populations | Only historical measurement is computable |

### 5.3 Blocked by absent external data

| Layer | Missing input | Consequence |
|---|---|---|
| L08 Inventory snapshot | Stock-on-hand | No current non-moving inventory, no actual dead stock |
| L09 Goods receipt | Receipt dates and quantities | No unit ageing, no FIFO layers, no return windows |
| L07 (receipt side) | Returns records | No proven stock increase from cancellations |
| L11 family B/D | On-hand + acquisition cost | No trapped capital, no financial exposure |
| L11 recommendations | Supplier, PO, warehouse, policy | No reorder, transfer or buy-back action |

### 5.4 Gating summary

Only three of the twelve layers are unblocked today. Five are blocked by a decision that
the owner has not taken. Four are blocked by data that does not exist. No amount of
engineering changes the last category.

---

## 6. Target schemas (proposal only)

The schemas below are proposals. They create nothing. Types are logical, not
vendor-specific. Nullability is stated because a non-nullable derived field is a promise
the foundation may not be able to keep.

### 6.1 `product_identity`

| Field | Type | Null | Description |
|---|---|---|---|
| `canonical_product_code` | text | no | Governed identifier; created only under an approved rule |
| `original_stock_code` | text | no | Exact source string |
| `alias_type` | enum | no | `EXACT`, `CASE_FOLD`, `EVIDENCE_MERGE` |
| `product_class` | enum | no | Physical / shipping / service / financial / promotional / administrative / unknown |
| `description_current` | text | yes | Latest observed description; null where none exists |
| `lifecycle_status` | enum | no | Active / discontinued / unknown (default `unknown`) |
| `unit_of_measure` | text | yes | Supplied by master data only |
| `warehouse_id` | text | yes | Reserved; absent until L08 exists |
| `decision_id` | text | yes | Identity decision reference |
| `valid_from` | date | no | Start of validity |
| `valid_to` | date | yes | End of validity; null means current |

### 6.2 `transaction_classification`

| Field | Type | Null | Description |
|---|---|---|---|
| `classification_id` | text | no | Unique entry identifier |
| `scope` | enum | no | `ROW` or `GROUP` |
| `source_row` | integer | yes | Required when `scope = ROW`; null for `GROUP` |
| `row_count` | integer | no | 1 for `ROW`; group size for `GROUP` |
| `proposed_category` | enum | no | Proposal; never canonical until approved |
| `financial_impact` | enum | no | `POSITIVE_VALUE`, `NEGATIVE_VALUE`, `ZERO_VALUE`, `NOT_APPLICABLE` |
| `physical_impact` | enum | no | `DECREASE`, `INCREASE`, `NONE`, `UNKNOWN` |
| `confidence_level` | enum | no | `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN` |
| `manual_review_required` | boolean | no | Durable flag |
| `rule_id` | text | no | Rule that claimed the row |
| `rule_set_version` | text | no | Version of the ordered rule set |
| `evidence_supporting` | text | no | Positive evidence |
| `evidence_contradicting` | text | yes | What weakens the conclusion |

### 6.3 `inventory_snapshot`

| Field | Type | Null | Description |
|---|---|---|---|
| `snapshot_id` | text | no | Unique snapshot row |
| `snapshot_date` | date | no | Position date |
| `product_identity_key` | text | no | Canonical product |
| `warehouse_id` | text | no | Location |
| `on_hand_qty` | numeric | no | Must be ≥ 0; negatives rejected |
| `reserved_qty` | numeric | yes | Optional reservation |
| `average_cost` | numeric | yes | Acquisition cost; never selling price |
| `currency` | text | yes | Declared currency |
| `source_system` | text | no | Origin system |
| `source_record_hash` | text | no | Record-level fingerprint |

### 6.4 `product_demand_summary`

| Field | Type | Null | Description |
|---|---|---|---|
| `product_identity_key` | text | no | Canonical product |
| `window_days` | integer | no | Declared observation window |
| `period_start` | date | no | Window start |
| `period_end` | date | no | Window end |
| `units_sold` | numeric | no | Sum over admissible rows |
| `invoice_count` | integer | no | Distinct invoices |
| `line_count` | integer | no | Source lines |
| `first_sale_date` | date | yes | Null when never sold |
| `last_sale_date` | date | yes | Null when never sold |
| `recency_days` | integer | yes | `period_end − last_sale_date` |
| `demand_cv` | numeric | yes | Monthly variance measure when sufficient periods exist |
| `data_quality_flag` | enum | no | Aggregate of unresolved anomalies affecting the product |
| `rule_set_version` | text | no | Classification version used |
| `threshold_set_version` | text | no | Not applicable at demand layer; reserved |

### 6.5 `dead_stock_detection`

| Field | Type | Null | Description |
|---|---|---|---|
| `detection_id` | text | no | Unique detection |
| `product_identity_key` | text | no | Canonical product |
| `detection_type` | enum | no | Historical non-moving / slow-moving / excess / aged / dead candidate |
| `window_days` | integer | no | Observation window |
| `threshold_id` | text | no | Registry reference |
| `indicators` | json | no | Indicator values used |
| `available_mask` | text | no | Which indicators were available |
| `confidence_label` | enum | no | Confidence band |
| `limitation_text` | text | no | What the detection does not mean |
| `requires_inputs` | text[] | no | Missing inputs for a stronger claim |
| `approval_reference` | text | yes | Null until approved |

---

## 7. Traceability contract

Every derived row in every layer must satisfy all five clauses.

| # | Clause | Testable form |
|---|---|---|
| T1 | **Source path** | A derived row maps to one or more `SourceRow` values, or to a group whose `RowCount` and member rows are recorded. |
| T2 | **Rule version** | The row records the rule-set, threshold-set and identity versions that produced it. |
| T3 | **Input versions** | The containing dataset records the version identifiers of every upstream dataset. |
| T4 | **Reconciliation** | The dataset records row counts and value totals before and after, with a stated tolerance. |
| T5 | **Immutability** | The dataset version is closed and hashed; any change produces a new version, never an edit. |

The traceability chain is therefore:

```
source file → SourceRow → staging row → validated row → classification entry
           → product identity → demand measure → detection → score → report cell
```

Each arrow carries a version. A break anywhere invalidates the downstream number.

### 7.1 Quarantine interaction

A quarantined row is still traceable. It retains its `SourceRow`, its failure code and
its batch identifier, and it remains countable in the reconciliation identity. Quarantine
is a state, not a deletion.

---

## 8. Explicit non-goals

1. This document does not implement any layer, pipeline, table, index or job.
2. It does not approve D01–D07, or any part of them.
3. It does not create V3, or authorise the creation of V3.
4. It does not claim that the existing V2 definition is a governance rule.
5. It does not define thresholds; it requires that thresholds be configurable and
   owner-approved.
6. It does not model, forecast or score anything.
7. It does not infer stock, cost, supplier, warehouse or returns data.
8. It does not replace the classification policy, the research document, the data
   requirements document or the architecture document.
9. It does not state that historical inactivity is dead stock.
10. It does not close any of the 93 open anomalies.

---

## 9. Open dependencies and approval register

| Ref | Question the owner must answer | Blocks |
|---|---|---|
| D01 | Is the A563185–A563187 group a financial adjustment excluded from product sales? | L06, L10, L11 |
| D02 | Is there a governed product-code registry, and what is each code family? | L04, L10, L11 |
| D03 | Is classification multi-dimensional (event / financial / physical)? | L05, L07, L11 |
| D04 | Are duplicates flagged rather than removed, and under what key? | L10, L11 |
| D05 | May zero-price rows ever be sales, and how do they enter inventory reasoning? | L05, L07, L11 |
| D06 | What is the canonical identity rule, and which merges are admissible? | L04, L10 |
| D07 | How are `UNKNOWN` and manual-review rows resolved, and by whom? | L05, L11 |
| X01 | Will inventory snapshots be supplied, at what grain and cadence? | L08, L11 B/D |
| X02 | Will goods receipts and purchase orders be supplied? | L09, L11 |
| X03 | Will acquisition cost and holding-rate components be supplied? | L11 D |
| X04 | Will supplier, warehouse and returns data be supplied? | L07, L11 recommendations |

**Every row above is `PENDING`.** No row is approved. The foundation described in this
document cannot be declared complete while any row remains open, because the layers that
depend on those rows are the layers that carry the product's central claims.

---

*End of design. Nothing in this document is implemented, approved or in force.*
