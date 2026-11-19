import json, sys, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from trexo.ml.config import *
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.forecasting.engine import *
from trexo.ml.registry.registry import save_model_bundle, data_fingerprint, feature_schema_fingerprint

t0 = time.time(); sales = load_sales()
mat_df, start = weekly_matrix(sales); mat = mat_df.to_numpy(float); codes = mat_df.index.to_numpy()
n_weeks = mat.shape[1]; print("products", len(codes), "complete weeks", n_weeks, "ends", start + pd.Timedelta(days=7 * n_weeks - 1))
ORIGINS = [36, 40, 44]            # forecast origins (weeks observed); 8-week targets end at week 52
MIN_ACTIVE = 4                    # sufficient-history rule (>=4 active weeks before origin)
methods = ["zero", "naive", "ma4", "ma8", "ses", "croston", "sba", "lightgbm"]
rows = []                          # per product-origin-horizon actual & forecasts
for o in ORIGINS:
    hist = mat[:, :o]; active = (hist > 0).sum(1)
    elig = np.flatnonzero(active >= MIN_ACTIVE)
    lgbm = fit_lgbm(mat, o - 1)               # trained on targets <= week o-1 only
    cls = [demand_class(hist[i]) for i in elig]
    cf = [classical_forecasts(hist[i]) for i in elig]
    for h in range(1, MAX_H + 1):
        if o + h - 1 >= n_weeks: break
        X = ml_features(mat, o, h)[elig]
        pl = np.clip(lgbm.predict(X), 0, None)
        for k, i in enumerate(elig):
            r = {"origin": o, "h": h, "StockCode": codes[i], "actual": mat[i, o + h - 1],
                 "demand_class": cls[k], "lightgbm": pl[k], **cf[k]}
            rows.append(r)
bt = pd.DataFrame(rows)
bt.to_csv(ML_DATA_DIR / "forecast_backtest_rows.csv.gz", index=False)
bt["horizon_group"] = np.where(bt["h"] <= 4, "short_1-4w", "medium_5-8w")
res = {"origins": ORIGINS, "min_active_weeks": MIN_ACTIVE, "n_rows": len(bt), "overall": {}, "by_horizon_group": {},
       "by_demand_class": {}, "cumulative_4w": {}}
for m in methods:
    res["overall"][m] = forecast_metrics(bt["actual"], bt[m])
    for g, d in bt.groupby("horizon_group"):
        res["by_horizon_group"].setdefault(g, {})[m] = forecast_metrics(d["actual"], d[m])
    for g, d in bt.groupby("demand_class"):
        res["by_demand_class"].setdefault(g, {})[m] = forecast_metrics(d["actual"], d[m])
cum = bt[bt["h"] <= 4].groupby(["origin", "StockCode"]).agg({**{m: "sum" for m in methods}, "actual": "sum"}).reset_index()
cum = cum[bt[bt["h"] <= 4].groupby(["origin", "StockCode"]).size().values == 4]
for m in methods: res["cumulative_4w"][m] = forecast_metrics(cum["actual"], cum[m])
# model selection per demand class by WAPE on pooled backtest (ties -> simpler method)
simple_order = ["zero", "naive", "ma4", "ma8", "ses", "croston", "sba", "lightgbm"]
choice = {}
for g, d in res["by_demand_class"].items():
    cand = {m: v["MAE"] for m, v in d.items() if m != "zero"}   # MAE: zero-safe, penalises over-forecasting too
    best = min(cand, key=lambda m: (round(cand[m], 6), simple_order.index(m)))
    choice[g] = best
res["selected_method_by_demand_class"] = choice
overall_best = min((m for m in methods if m != "zero"), key=lambda m: res["overall"][m]["MAE"])
res["overall_best_by_MAE"] = overall_best
res["zero_forecast_note"] = "zero forecast reported as a sanity floor for intermittent series"
# fallback for insufficient history: MA8 (documented); final production model fits all weeks
final = fit_lgbm(mat, n_weeks - 1)
meta = save_model_bundle("forecasting", {"lightgbm": final},
    {"features": ML_FEATURE_NAMES, "weeks_in_training": n_weeks, "week_zero": str(start.date()),
     "selected_method_by_demand_class": choice, "fallback_method": "ma8", "min_active_weeks": MIN_ACTIVE,
     "max_horizon_weeks": MAX_H, "backtest_origins": ORIGINS, "overall_backtest": res["overall"], "random_seed": SEED,
     "feature_schema": ML_FEATURE_NAMES,
     "feature_schema_sha256": feature_schema_fingerprint(ML_FEATURE_NAMES),
     "training_data_fingerprint": data_fingerprint([ML_DATA_DIR / "valid_sales_v1.csv.gz",
                                                    ML_DATA_DIR / "data_manifest_v1.json"])})
res["artifact"] = meta; res["trained_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
(REPORT_DIR / "forecasting_results.json").write_text(json.dumps(res, indent=2, default=str))
print(f"{'method':10s} {'MAE':>7s} {'RMSE':>8s} {'WAPE':>7s} {'sMAPE':>7s} {'bias':>7s}")
for m in methods:
    x = res["overall"][m]; print(f"{m:10s} {x['MAE']:7.3f} {x['RMSE']:8.2f} {x['WAPE']:7.3f} {x['sMAPE']:7.3f} {x['bias']:7.3f}")
print(choice, "time", round(time.time() - t0, 1))
