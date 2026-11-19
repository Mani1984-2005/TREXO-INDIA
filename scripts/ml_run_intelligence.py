"""Run all intelligence modules at the evaluation date and write outputs + movement/anomaly artifacts."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from trexo.ml.config import *
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.features.product_features import build_features
from trexo.ml.dead_stock.classifier import classify_products, _load_rule_curve
from trexo.ml.movement.movement import classify_movement
from trexo.ml.forecasting.engine import weekly_matrix
from trexo.ml.forecasting.predict import forecast_products
from trexo.ml.recommendations.engine import build_queue, UNAVAILABLE_ACTIONS
from trexo.ml.decision_engine.engine import management_summary
from trexo.ml.anomaly import detector as an
from trexo.ml.financial.intelligence import data_readiness
from trexo.ml.registry.registry import (load_model_bundle, save_model_bundle,
                                        data_fingerprint, feature_schema_fingerprint)
from trexo.ml.config import load_calibrated_thresholds

sales = load_sales(); desc = pd.read_csv(ML_DATA_DIR / "product_descriptions_v1.csv", dtype=str)
as_of = sales["Date"].max(); print("as of", as_of.date())
feat = build_features(sales, as_of)
curve = _load_rule_curve(); t = load_calibrated_thresholds()
cls = classify_products(feat, sales, desc)
dead_days = curve[2]["recency_days_at_probability"]["0.6"]
mov = classify_movement(feat, sales, dead_days)
# forecasts
objs, fmeta = load_model_bundle("forecasting")
mat_df, _ = weekly_matrix(sales)
fc = forecast_products(mat_df, fmeta["selected_method_by_demand_class"], objs["lightgbm"])
fc4w = fc[fc["horizon_week"] <= 4].groupby("StockCode")["forecast_units"].sum()
fc.to_csv(REPORT_DIR / "forecast_next_8_weeks.csv", index=False)
queue = build_queue(cls, mov, fc4w)
queue.to_csv(REPORT_DIR / "dead_stock_intervention_queue.csv", index=False)
cls_cols = ["StockCode", "Description", "classification", "dead_stock_risk_score", "days_since_last_sale", "total_qty",
            "velocity_per_day", "risk_explanation", "recommended_intervention", "evidence_quality", "evidence_flags",
            "demand_pattern", "status_type"]
cls[cls_cols].sort_values("dead_stock_risk_score", ascending=False).to_csv(REPORT_DIR / "dead_stock_classification.csv", index=False)
mov.to_csv(REPORT_DIR / "product_movement_classification.csv", index=False)
# anomaly
tq = an.transaction_quality(sales); tq.to_csv(REPORT_DIR / "anomaly_transaction_quality.csv", index=False)
da = an.demand_anomalies(mat_df); da.to_csv(REPORT_DIR / "anomaly_business_demand.csv", index=False)
iforest = an.fit_isolation_forest(feat); ifs = an.score_isolation_forest(iforest, feat)
ifs.merge(desc, on="StockCode", how="left").sort_values("anomaly_score", ascending=False).to_csv(REPORT_DIR / "anomaly_product_profile_isolation_forest.csv", index=False)
save_model_bundle("anomaly", {"isolation_forest": iforest},
                  {"features": an.IF_FEATURES, "contamination": 0.02,
                   "fit_as_of": str(as_of.date()), "random_seed": SEED,
                   "family": "BUSINESS_DEMAND product profile",
                   "feature_schema_sha256": feature_schema_fingerprint(an.IF_FEATURES),
                   "training_data_fingerprint": data_fingerprint([ML_DATA_DIR / "valid_sales_v1.csv.gz",
                                                                  ML_DATA_DIR / "data_manifest_v1.json"])})
# movement thresholds artifact (population statistics used by single-product inference)
act = feat["days_since_last_sale"] <= dead_days
save_model_bundle("movement", {"population": {
    "dead_recency_days": dead_days, "velocity_q_fast": float(feat.loc[act, "velocity_per_day"].quantile(t.fast_velocity_pctl)),
    "velocity_q_slow": float(feat.loc[act, "velocity_per_day"].quantile(1 - t.fast_velocity_pctl)),
    "revenue_sorted_desc": np.sort(mov["revenue_to_date"].to_numpy())[::-1]}},
    {"thresholds": t.__dict__, "fit_as_of": str(as_of.date()),
     "note": "rule-based; population statistics, not a fitted estimator",
     "training_data_fingerprint": data_fingerprint([ML_DATA_DIR / "valid_sales_v1.csv.gz",
                                                    ML_DATA_DIR / "data_manifest_v1.json"])})
# financial readiness
raw_cols = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
data_readiness(raw_cols).to_csv(REPORT_DIR / "financial_data_readiness.csv", index=False)
# decision summary
summ = management_summary(cls, mov, queue, fc4w, str(as_of.date()))
summ["unavailable_actions_need_data"] = UNAVAILABLE_ACTIONS
(REPORT_DIR / "management_summary.json").write_text(json.dumps(summ, indent=2, default=str))
print(json.dumps({k: summ[k] for k in ["classification_counts", "priority_counts", "historical_revenue_share_of_critical_and_atrisk_products", "do_not_reorder_count_evidence_not_low"]}, indent=2))
print("transaction-quality flagged:", len(tq), tq["flags"].value_counts().head(6).to_dict())
print("demand anomalies:", da["type"].value_counts().to_dict(), "IF anomalous:", int(ifs["is_anomalous_profile"].sum()))
print(queue[["queue_rank","StockCode","Description","priority","classification","dead_stock_risk_score","abc_xyz"]].head(8).to_string())
