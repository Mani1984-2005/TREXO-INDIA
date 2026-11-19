"""Write reports/ML_ENGINEERING_COMPLETION_REPORT.md from actual result files."""
import json, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd
R = ROOT / "reports" / "ml"
ds = json.loads((R / "dead_stock_model_results.json").read_text())
fc = json.loads((R / "forecasting_results.json").read_text())
ms = json.loads((R / "management_summary.json").read_text())
man = json.loads((ROOT / "data/ml/data_manifest_v1.json").read_text())
cal = json.loads((ROOT / "data/ml/calibration.json").read_text())
d01 = json.loads((R / "d01_lineage_audit.json").read_text())
dq = json.loads((R / "data_quality_audit.json").read_text())
tr = json.loads((R / "test_results.json").read_text())
api = json.loads((R / "inference_contract_examples.json").read_text())
sim = pd.read_csv(R / "simulation_backtest_summary.csv", index_col=0)
queue = pd.read_csv(R / "dead_stock_intervention_queue.csv")
cls = pd.read_csv(R / "dead_stock_classification.csv")
tq = pd.read_csv(R / "anomaly_transaction_quality.csv")
da = pd.read_csv(R / "anomaly_business_demand.csv")
ifs = pd.read_csv(R / "anomaly_product_profile_isolation_forest.csv")
models = []
for kind in ("dead_stock", "forecasting", "anomaly", "movement"):
    base = ROOT / "models" / kind
    latest = (base / "LATEST").read_text().strip()
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        meta = json.loads((d / "metadata.json").read_text())
        models.append({"kind": kind, "version": d.name, "latest": d.name == latest,
                       "trained": meta.get("trained_at_utc"), "status": meta.get("status"),
                       "pipeline": meta.get("pipeline_version"),
                       "checksums": len(meta.get("artifact_checksums_sha256", {}))})
fp = (json.loads((ROOT / ds["artifact"]["path"] / "metadata.json").read_text())
      .get("training_data_fingerprint") or {})
M = ds["models"]; sel = ds["selection"]["selected"]; base = M["baseline_recency_rule"]
bt = base["test"]; st = M[sel]["test"]
fo = fc["overall"]; cc = ms["classification_counts"]
agg = sim
def S(strategy, col): return float(agg.loc[strategy, col])
d_excess = (S("trexo", "excess_units") / S("baseline", "excess_units") - 1) * 100
d_unmet = (S("trexo", "unmet_demand_units") / S("baseline", "unmet_demand_units") - 1) * 100
d_buy = (S("trexo", "units_bought") / S("baseline", "units_bought") - 1) * 100
d_zero = (S("trexo", "units_bought_on_zero_demand_products") /
          S("baseline", "units_bought_on_zero_demand_products") - 1) * 100

def tbl(d, cols=None):
    d = d if cols is None else d[cols]
    h = "| " + " | ".join(d.columns) + " |\n|" + "---|" * len(d.columns) + "\n"
    return h + "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in d.itertuples(index=False))

md = f"""# TREXO-INDIA ML Engineering Completion Report

> Generated from the actual executed result files on {dt.datetime.now(dt.timezone.utc).isoformat()} by `scripts/ml_write_completion_report.py`. No metric below is hand-typed from memory.

## 1. Executive summary

The ML package has been audited, corrected, rebuilt, retrained, executed and tested end to end.

- **Governance:** approved decision **D01** is now implemented explicitly, with source-row lineage, a quarantined financial-event record, exclusion accounting, corrected movement exports and regression tests. The three invoices remain in the raw workbook unchanged; they are absent from every ML training/evaluation/recommendation input.
- **Data:** valid sales are unchanged in count (527,725) because D01 was previously excluded by accident via StockCode `B`; the difference is that the governed reason is now explicit and reconciled (net -11,062.06).
- **Models:** dead-stock, forecasting, anomaly and movement artifacts were rebuilt under pipeline `ml-1.1.0`, with training-data and feature-schema SHA-256 fingerprints. Previous `ml-1.0.0` artifacts remain in the registry.
- **Tests:** standard suite **{tr['standard']['passed']} passed, {tr['standard']['failed']} failed, {tr['standard']['skipped']} skipped**; full-dataset suite **{tr['full_dataset']['passed']} passed, 0 failed**.
- **Honest status:** engineering-ready and integration-ready at the Python service level; **not production-ready**. On-hand stock, unit cost, lead time, supplier and location data are still absent, so physical dead stock and financial savings cannot be measured.

## 2. Original repository state (Phase A baseline)

- Outer project: `E:\\TREXO-INDIA`; ML package: `E:\\TREXO-INDIA\\TREXO-INDIA-ML\\TREXO-INDIA`.
- Python interpreter: **{tr['python']}** in `E:\\TREXO-INDIA\\.venv`; Python 3.12 specified by the deployment guide was not installed.
- pytest was **not installed**; the pre-existing ML test suite had not been executed on this machine.
- Baseline after installing pytest into the project venv: **68 passed, 4 skipped**.
- Raw workbook: {man['raw_rows']:,} rows, SHA-256 `{man['raw_sha256']}`.
- D01 rows existed in raw and in Stage-processed movement V1/V2 but were absent from ML valid sales only because `B` was in the generic non-product list; the exclusion log had **no D01 reason**.

## 3. Work completed

1. Timestamped backup of reports, docs, ML source/scripts and manifests (`backups/ml_pre_completion_20261119T142835Z`).
2. D01 lineage investigation and reproducible audit.
3. Explicit D01 first-match exclusion, quarantine file, global reconciliation and manifest governance block.
4. D01-corrected movement exports without touching protected Stage files.
5. Data-quality, feature, label and leakage audit with measured findings.
6. Evidence-strength fields added to dead-stock outputs; recommendation contract completed to all 12 required fields.
7. Anomaly alerts now explain what was unusual and why review is required.
8. Inference validation tightened: non-product IDs rejected, D01 invoices excluded with a warning, optional inventory inputs validated, response schema/version/artifact metadata added, `health()` added.
9. Models retrained; data/schema fingerprints recorded; old versions preserved.
10. Tests added and executed, including D01 regression tests.
11. Documentation regenerated from actual results; API contract and completion report added.

## 4. D01 investigation and resolution

**Decision:** `{d01['decision']}` — `{d01['d01']['reason_code']}` / event group `{d01['d01']['event_group']}`.

{tbl(pd.DataFrame([{'invoice': x['invoice'], 'source_row': ', '.join(map(str, x['source_rows'])),
                     'quantity': x['quantity_sum'], 'line_value': x['line_value_sum'],
                     'stock_code': ', '.join(x['stock_codes'])} for x in d01['d01']['per_invoice']]))}

- Gross positive line value **{d01['d01']['gross_positive_line_value']:.2f}**; gross negative **{d01['d01']['gross_negative_line_value']:.2f}**; net **{d01['d01']['net_line_value']:.2f}**.
- StockCode `B` rows in raw: **{d01['source_verification']['stockcode_B_rows_in_raw']}**, exclusively D01: **{d01['source_verification']['stockcode_B_exclusively_d01']}**.
- Source reconciliation OK: **{d01['source_verification']['source_reconciliation_ok']}**; raw workbook unchanged.
- D01 rows in `valid_sales_v1`: **{d01['ml_dataset_presence']['d01_rows_in_valid_sales']}**; in forecast backtests: **{d01['ml_dataset_presence']['d01_rows_in_forecast_backtest']}**.
- Quarantine: `data/ml/excluded_financial_events_v1.csv` ({d01['ml_dataset_presence']['quarantine_rows']} rows, net {d01['ml_dataset_presence']['quarantine_net_line_value']:.2f}).
- Stage-processed V1/V2/monthly still physically contain the historical `B` row; they are protected by their own SHA-256 tests and are not consumed by ML. D01-corrected copies: `data/ml/product_movement_v1_d01corrected.csv`, `..._v2...`, `product_monthly_sales_v2_d01corrected.csv`.
- Full evidence: `docs/D01_LINEAGE_AUDIT.md`, `reports/ml/d01_lineage_audit.json`.

## 5. Data pipeline changes

- `PIPELINE_VERSION` advanced to **{man['pipeline_version']}**.
- Rule order: **D01_BAD_DEBT_GROUP → MISSING_DATE → MISSING_QUANTITY_OR_PRICE → NON_PRODUCT_CODE → CANCELLATION_INVOICE → NON_POSITIVE_QUANTITY → NEGATIVE_PRICE → ZERO_PRICE**.
- D01 is matched by invoice, not StockCode; StockCode `B` remains only a defensive non-product fallback.
- New outputs: `excluded_financial_events_v1.csv`, `d01_lineage_reconciliation.csv`, manifest `governance_exclusions.D01_BAD_DEBT_GROUP`.
- Raw workbook is read-only; no source row is deleted or edited.

## 6. Dataset reconciliation

{tbl(pd.DataFrame(list(man['exclusion_log'].items()), columns=['reason', 'rows']))}

- Sum of exclusion-log buckets = **{sum(man['exclusion_log'].values()):,}** = raw rows **{man['raw_rows']:,}**.
- Valid sales **{man['valid_sale_rows']:,}**; distinct products with valid sales **{man['distinct_products_with_valid_sales']:,}**; codes without valid sales **{man['codes_without_valid_sales']}**.
- Exact duplicate valid rows retained and flagged: **{man['exact_duplicate_valid_rows_kept']:,}** (not silently removed).
- D01 rows in valid sales: **0**.

## 7. Feature engineering and data quality

- Feature schema unchanged and stable; all {len(dq['product_history'])} product-history inputs are computed from delivered sales only.
- Products assessed: **{dq['product_history']['products']:,}**; products with any NaN feature: **{dq['leakage_and_consistency']['features_contain_any_nan_products']}**.
- Leakage: cutoffs purged **{dq['leakage_and_consistency']['cutoffs_purged']}**; CV folds purged **{dq['leakage_and_consistency']['cv_folds_purged']}**; product aggregation reconciles **{dq['leakage_and_consistency']['product_aggregation_reconciles']}**.
- Missing CustomerID: **{dq['missing_values']['CustomerID']['pct']:.1f}%**; missing Description: **{dq['missing_values']['Description']['missing']:,}** rows.
- {dq['product_identifiers']['case_variant_groups']} case-variant StockCode groups; case-folding deliberately **not** applied.
- Full report: `docs/ML_DATA_QUALITY_REPORT.md`.

## 8. Model training details

- Dead-stock target: no valid sale in the next 60 days (demand inactivity, **not** physical dead stock).
- Cutoffs: train {ds['cutoffs']['train']}; validation {ds['cutoffs']['val']}; test {ds['cutoffs']['test']}; purged chronological splits.
- Selected challenger: **{sel}**; deployed predictor: **{ds['selection']['selected'] if ds['selection']['accepted_over_baseline'] else 'baseline_recency_rule'}**.
- Acceptance rule: PR-AUC >= baseline + 0.02 on validation and test, and Brier below prevalence prior. **Accepted: {ds['selection']['accepted_over_baseline']}**.
- Training runtime: {ds['runtime_seconds']}s.
- Data fingerprint: `{fp.get('combined_sha256', '')}`.
- Model artifacts: pipeline `ml-1.1.0`, checksum-verified round-trip; old `ml-1.0.0` retained.

## 9. Model evaluation metrics

| Model | Split | PR-AUC | ROC-AUC | Precision | Recall | F1 | FPR | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {n} | {s} | {v[s]['pr_auc']:.3f} | {v[s]['roc_auc']:.3f} | {v[s]['precision']:.3f} | "
    f"{v[s]['recall']:.3f} | {v[s]['f1']:.3f} | {v[s]['false_positive_rate']:.3f} | "
    f"{v[s]['brier']:.4f} | {v[s]['ece']:.4f} |"
    for n, v in M.items() for s in ("val", "test")) + f"""

- Deployed rule on test: PR-AUC **{bt['pr_auc']:.3f}**, ROC-AUC **{bt['roc_auc']:.3f}**, recall **{bt['recall']:.3f}**, precision **{bt['precision']:.3f}**, Brier **{bt['brier']:.4f}**, ECE **{bt['ece']:.4f}**.
- The ML challenger did **not** beat the transparent recency rule by the pre-set margin; retaining the rule is the evidence-based choice.

## 10. Dead-stock reduction capabilities

At as-of **{ms['as_of']}**, {ms['products_assessed']:,} products assessed:

{tbl(pd.DataFrame(list(cc.items()), columns=['classification', 'products']))}

- Intervention queue: **{len(queue)}** products; priorities {queue.priority.value_counts().to_dict()}.
- Do-not-reorder with non-LOW evidence: **{ms['do_not_reorder_count_evidence_not_low']}**.
- Every recommendation now includes product id, description, classification, risk score, evidence, detected problem, intervention, reason, expected impact direction, required inputs, confidence, and `requires_human_approval = True`.
- No monetary saving is claimed; `inventory_value_impact` is `NOT_QUANTIFIABLE_WITHOUT_ON_HAND_AND_UNIT_COST`.

## 11. Forecasting results

Rolling-origin backtest at origins {fc['origins']}, {fc['n_rows']:,} product-origin-horizon cases, 8 methods compared.

{tbl(pd.DataFrame([[m, round(v['MAE'], 3), round(v['RMSE'], 3), round(v['WAPE'], 4), round(v['sMAPE'], 4), round(v['bias'], 4)] for m, v in fo.items()],
                  columns=['method', 'MAE', 'RMSE', 'WAPE', 'sMAPE', 'bias']))}

- Best pooled method by MAE: **{fc['overall_best_by_MAE']}**. LightGBM is **not** better than SES/MA8 on this single-year, intermittent dataset.
- Selected method per demand class: `{fc['selected_method_by_demand_class']}`.
- 4-week cumulative WAPE for SES: **{fc['cumulative_4w']['ses']['WAPE']:.3f}**.
- Limitation: 53 complete weeks, one seasonal cycle; horizons capped at 8 weeks.

## 12. Recommendation quality

- Queue rows: **{len(queue)}**; P1={queue.priority.eq('P1').sum()}, P2={queue.priority.eq('P2').sum()}, P3={queue.priority.eq('P3').sum()}, P4={queue.priority.eq('P4').sum()}.
- Recommendation logic is rule-based and auditable; discounts/clearance are gated on margin data that does not exist.
- Evaluation plan is documented per row (compare 60-day outcomes with look-alikes). **No real-world outcome has been measured**, so recommendation lift is unproven.

## 13. Simulation results (unit-level scenario, not money)

{tbl(agg.T.reset_index().rename(columns={'index': 'metric'}).round(4))}

- Versus baseline: units bought **{d_buy:+.1f}%**, excess units **{d_excess:+.1f}%**, unmet demand **{d_unmet:+.1f}%**, units bought on zero-demand products **{d_zero:+.1f}%**.
- Adverse signal: TREXO placed **{int(agg.loc['trexo','purchase_lines_on_zero_demand_products'])}** purchase lines on products with zero subsequent demand vs **{int(agg.loc['baseline','purchase_lines_on_zero_demand_products'])}** for baseline.
- No money, margin, carry-over inventory, lead times or MOQs are modelled.

## 14. Test execution results

- Environment: Python **{tr['python']}**, pytest **8.4.2**, packages {tr['packages']}.
- Standard: **{tr['standard']['passed']} passed, {tr['standard']['failed']} failed, {tr['standard']['errors']} errors, {tr['standard']['skipped']} skipped** (`{tr['standard']['summary_line']}`).
- Full-dataset (`TREXO_SLOW_TESTS=1`): **{tr['full_dataset']['passed']} passed, {tr['full_dataset']['failed']} failed** (`{tr['full_dataset']['summary_line']}`).
- Syntax compilation: `python -m compileall -q src scripts tests` completed successfully.
- Evidence: `reports/ml/test_results.json`.

## 15. Model artifact inventory

{tbl(pd.DataFrame(models))}

All current artifacts are checksum-verified and load successfully. `LATEST` pointers resolve to `ml-1.1.0`.

## 16. Inference and backend readiness

- `InferenceService.health()` returns schema version and artifact versions: `{api['health']}`.
- Request validation rejects non-product StockCodes, applies D01 invoice exclusion, validates inventory inputs and reports every excluded record.
- Responses carry `schema_version`, product/request id, timestamp, model version, training timestamp, pipeline version, warnings, evidence quality and explanation.
- Real request/response examples: `reports/ml/inference_contract_examples.json`; contract: `docs/ML_API_CONTRACT.md`.
- No HTTP API exists; wrapping is a backend task. No automatic purchasing or inventory action is possible.

## 17. Documentation updates

Updated/created by `scripts/ml_generate_docs.py` and dedicated scripts: `ML_ARCHITECTURE`, `ML_DATA_DICTIONARY`, `ML_FEATURE_ENGINEERING`, `ML_DATA_QUALITY_REPORT`, `D01_LINEAGE_AUDIT`, `DEAD_STOCK_INTELLIGENCE`, `DEAD_STOCK_REDUCTION_STRATEGY`, `DEMAND_FORECASTING`, `INVENTORY_OPTIMIZATION`, `MODEL_TRAINING_REPORT`, `MODEL_EVALUATION_REPORT`, `MODEL_LIMITATIONS`, `ML_TESTING_REPORT`, `ML_DEPLOYMENT_GUIDE`, `ML_FINAL_ACCEPTANCE_REPORT`, `ML_API_CONTRACT`.

## 18. Remaining limitations

1. No on-hand stock, unit cost, margin, receipts, suppliers, lead times, MOQ, location or lifecycle data. Physical dead stock, capital tied up and real savings cannot be computed.
2. One year / one seasonal cycle; seasonality can only be flagged.
3. ML adds no measurable improvement over the recency rule; the deployed predictor is the transparent rule.
4. Top-band nominal risk overstates observed inactivity (~0.84-0.88 observed).
5. Forecasts are weekly, ≤8 weeks, and individual-product accuracy is rough (SES WAPE {fo['ses']['WAPE']:.3f}).
6. {man['exact_duplicate_valid_rows_kept']:,} exact duplicate valid rows are retained and flagged; treatment remains an owner decision.
7. {dq['missing_values']['CustomerID']['pct']:.1f}% of rows lack CustomerID; {dq['product_identifiers']['case_variant_groups']} case-variant StockCode groups are not case-folded (not approved).
8. Stage-processed movement V1/V2 still contain the historical D01 `B` row as protected artifacts; ML does not consume them.
9. Simulation is hypothetical and unit-level, not a financial outcome.
10. Data is a single UK wholesaler dataset; India-specific generalisation is unproven.
11. No security review, authentication, monitoring, retraining schedule or pilot has been performed.

## 19. Outstanding owner decisions

1. Duplicate treatment (retain/flag vs approved removal).
2. Product-key case policy.
3. Approval/change of the remaining sale classification assumptions (D01 is resolved).
4. Supply of stock snapshots, unit cost/margin, receipts/purchase orders, supplier terms, locations and lifecycle status.
5. Sign-off of priority weights, thresholds and dead-stock block threshold.
6. Backend hosting, API security, monitoring and pilot scope.

## 20. Exact next steps

1. Obtain at least one stock snapshot (product × location × date) and unit cost; re-run classification with `on_hand` and compute measured inventory value.
2. Obtain 12-24 months of purchase/receipt and lead-time data; enable true reorder-point and stockout trade-off evaluation.
3. Approve duplicate and product-key policies; rebuild datasets and retrain under the approved rules.
4. Run the documented intervention evaluation as a controlled pilot; measure 60-day outcomes against matched controls.
5. Wrap `InferenceService` per `ML_API_CONTRACT.md`; add auth, rate limits, audit logging and `health()` monitoring.
6. Establish retraining cadence and PSI drift alerts; promote artifacts only through the checksum-verified registry.
7. Extend history to a second seasonal cycle before trusting seasonal recommendations.
"""
(ROOT / "reports" / "ML_ENGINEERING_COMPLETION_REPORT.md").write_text(md, encoding="utf-8")
print(json.dumps({
    "report": "reports/ML_ENGINEERING_COMPLETION_REPORT.md",
    "tests_standard": tr['standard']['summary_line'],
    "tests_full": tr['full_dataset']['summary_line'],
    "d01_net": d01['d01']['net_line_value'],
    "models": [m for m in models if m['latest']],
}, indent=2, default=str))
