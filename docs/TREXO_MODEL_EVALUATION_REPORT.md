# TREXO Model Evaluation Report

**Date:** 2026-11-20
**Artifacts evaluated:** `models/dead_stock/dead_stock-ml-1.1.0-20261120T122808Z`, `models/forecasting/forecasting-ml-1.1.0-20261120T122830Z`, retail artifacts under `models/{pricing,bundles,customers,forecasting_price}`.
**Independent script:** `scripts/ml_independent_evaluation.py` → `reports/ml/independent_evaluation.json`

---

## 1. Method

The independent evaluation deliberately avoids the training pipeline's own metric code:

- data loaded through the public `trexo.ml.data_pipeline.pipeline.load_sales`;
- training/validation/test tables rebuilt with the public feature and label functions;
- recency calibration fitted on **training cutoffs only** (no test information);
- threshold selected on validation by F2, computed inline;
- test metrics computed directly with scikit-learn (`roc_auc_score`, `average_precision_score`, `brier_score_loss`, `confusion_matrix`);
- the registry artifact is **not** used for out-of-time numbers, because it is intentionally refit on all labelled cutoffs. Using it on the test cutoff would be in-sample.

---

## 2. Dead-stock rule — independent results

### Validation cutoff (2011-08-10, n = 3,583, prevalence 0.2219)

| Metric | Value |
|---|---:|
| ROC-AUC | 0.923939 |
| PR-AUC | 0.761127 |
| Brier | 0.088156 |
| Brier (prevalence prior) | 0.172650 |
| Threshold (F2) | 0.231788 |
| Precision | 0.588089 |
| Recall | 0.894340 |
| F1 | 0.709581 |
| F2 | 0.809979 |

### Untouched test cutoff (2011-10-10, n = 3,765, prevalence 0.2048)

| Metric | Value |
|---|---:|
| ROC-AUC | 0.946921 |
| PR-AUC | 0.801979 |
| Brier | 0.070406 |
| Brier (prevalence prior) | 0.162846 |
| Threshold | 0.231788 |
| Precision | 0.635539 |
| Recall | 0.909209 |
| F1 | 0.748132 |
| F2 | 0.837115 |
| Confusion (TN/FP/FN/TP) | 2592 / 402 / 70 / 701 |

### Consistency with the registered report

The registered `reports/ml/dead_stock_model_results.json` records the same test PR-AUC (`0.801978787703206`) and ROC-AUC (`0.946921296115794`). The independent recomputation agrees to machine precision, which rules out a mismatch between the reported and actual behaviour of the deployed rule on this split.

### Interpretation

- The rule is well calibrated relative to the prevalence prior (Brier 0.070 vs 0.163).
- Recall is high by design (F2 threshold): the shop is warned about most demand-inactive products at the cost of ~18% false positives on the test split.
- Precision of 0.636 means roughly one in three alerts is a product that will still sell. Alerts must be treated as review prompts, not write-offs.
- **The target is demand inactivity over 60 days, not physical dead stock.** Without stock-on-hand and cost data, capital trapped cannot be computed.

---

## 3. Challenger assessment

| Candidate | Test PR-AUC | Accepted |
|---|---:|---|
| Calibrated recency rule (deployed) | 0.8020 | baseline |
| Histogram gradient boosting | 0.7926 raw / 0.7838 calibrated | **No** |
| LightGBM | 0.780 | No |
| Random forest | 0.779 | No |
| Logistic regression | 0.793 | No |

Reasons for rejection:

1. The required improvement margin (PR-AUC ≥ baseline + 0.02 on validation **and** test) was not met on either split.
2. The challenger's calibrated PR-AUC is lower than the simpler rule's.
3. Seed stability is perfect (std = 0.0) but irrelevant when the point estimate is below the baseline.
4. A more complex model with no measured gain adds maintenance and explanation cost.

The rejected estimator remains registered for audit and can be re-evaluated when real inventory data arrives.

---

## 4. Forecasting evaluation

Backtest: 3 origins (weeks 36, 40, 44), 75,704 rows, actual 3,070,561 units.

| Method | WAPE | MAE | Bias |
|---|---:|---:|---:|
| SES (selected) | 0.7112 | 28.85 | −0.160 |
| MA8 | 0.7221 | 29.29 | −0.207 |
| LightGBM | 0.7273 | 29.50 | −0.142 |
| MA4 | 0.7336 | 29.75 | −0.153 |
| Naive | 0.8144 | 33.03 | −0.125 |
| SBA | 0.830 | 33.66 | −0.321 |
| Croston | 0.837 | 33.96 | −0.285 |
| Zero | 1.000 | 40.56 | −1.000 |

Per-class selection: smooth→SES, intermittent→MA8, erratic→SBA, lumpy→SES.

Negative bias means the methods under-forecast on this dataset. The 4-week cumulative view and the zero-forecast sanity floor are recorded in `reports/ml/forecasting_results.json`. Forecasts are planning inputs, not commitments.

---

## 5. Retail model evaluation

| Component | Metric | Result | Caveat |
|---|---|---|---|
| Pooled price elasticity | coefficient (95% CI) | −0.7365 (−0.8044, −0.7043) | observational, prices set by the business |
| Elasticity placebo | permuted-price coefficient | 0.0038 | passes |
| Elasticity split-half | first / second half | −0.598 / −0.671 | stable sign and magnitude |
| Price-aware forecast | WAPE vs SES | 0.6952 vs 0.7112 | ~2% gain, scenario use only |
| Price-aware forecast | MAE gain vs SES (95% CI) | 0.65 (0.13, 1.17) | small |
| Bundle rules | share keeping lift > 1 in holdout | 82.1% | association, not causation |
| Bundle rules | train↔test lift Spearman | 0.7852 | strong rank stability |
| Recommender | hit-rate@10 | 46.2% vs 33.8% popularity | aggregate default, consent-gated |
| Customer segments | k = 4 RFM groups | 4,334 customers | descriptive, no performance claim |
| Discount-proxy | train/test Spearman | ≈ 0.49 | proxy only |
| MILP optimiser | brute-force equality | exact | synthetic constraints |
| Clearance replay | simulated benefit | **none demonstrated** | assumptions A1–A3 |

---

## 6. Data and leakage controls

- **D01:** invoices `A563185`, `A563186`, `A563187` are excluded from training and inference; the independent evaluation confirms zero records in the valid-sales file. Original records are untouched.
- **Time ordering:** all labels are computed strictly after the cutoff; features never see future rows. Purged forward-chaining CV is used for tuning.
- **Price-aware forecast:** only data up to the origin plus the *planned* target-week price is used.
- **Bundle/recommender:** chronological split (train Dec 2010–Aug 2011, test Sep–Dec 2011).
- **Backtest:** origins and horizons are fixed and reported.

---

## 7. Evaluation limits

1. The UCI dataset has no stock-on-hand, cost or receipt data: trapped capital and margin impact are **not computable**.
2. The test window is a single chronological holdout; no second year of data exists.
3. Retail simulations use labelled assumptions and demonstrate no real-shop profit benefit.
4. The store demo's ML history is synthetic and must never be used as evidence of model performance.

## 8. Verdict

| Question | Answer |
|---|---|
| Is the deployed dead-stock rule reproducible? | Yes, byte-identical artifacts and independently reproduced metrics |
| Is it better than the ML challenger on this data? | Yes, on PR-AUC and calibration |
| Is it production-ready? | No — decision support only; needs real inventory and pilot evaluation |
| Is the price-aware forecast a proven profit lever? | No — small accuracy gain, scenario use only |
