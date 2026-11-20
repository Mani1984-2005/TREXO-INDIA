"""Does knowing the (planned) price improve weekly demand forecasts versus the existing validated methods?
Same origins/horizons/eligibility as scripts/ml_train_forecasting.py. Existing models are NOT replaced unless this wins."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, lightgbm as lgb
from trexo.ml.config import REPORT_DIR, ML_DATA_DIR, SEED
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.forecasting.engine import weekly_matrix, ml_features, classical_forecasts, forecast_metrics, MAX_H, ML_FEATURE_NAMES, fit_lgbm
sales = load_sales(); mat_df, start = weekly_matrix(sales); mat = mat_df.to_numpy(float); codes = mat_df.index.to_numpy(); n_w = mat.shape[1]
s = sales.assign(w=(sales["Date"] - start).dt.days // 7); s = s[s["w"] < n_w]
pw = s.groupby(["StockCode", "w"])["UnitPrice"].median().unstack().reindex(index=codes, columns=range(n_w))
pw = pw.ffill(axis=1).bfill(axis=1); P = np.log(pw.to_numpy(float))          # log weekly median price, carried forward over no-sale weeks

def price_feats(o, h):
    prev = np.nanmean(P[:, max(0, o - 8):o], axis=1); t = o + h - 1
    return np.column_stack([P[:, t] - prev, P[:, o - 1] - P[:, max(0, o - 2)], P[:, o - 1] - prev])
def table(last_target, with_price, min_origin=12):
    X, y = [], []
    for o in range(min_origin, last_target + 1):
        for h in range(1, MAX_H + 1):
            if o + h - 1 > last_target: break
            f = ml_features(mat, o, h); f = np.column_stack([f, price_feats(o, h)]) if with_price else f
            X.append(f); y.append(mat[:, o + h - 1])
    X = np.vstack(X); y = np.concatenate(y); keep = X[:, ML_FEATURE_NAMES.index("active_weeks")] > 0
    return X[keep], y[keep]
def fit(last_target, with_price):
    X, y = table(last_target, with_price)
    return lgb.LGBMRegressor(objective="tweedie", tweedie_variance_power=1.3, n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=50,
                             subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1, n_jobs=2).fit(X, y)
rows = []
for o in (36, 40, 44):
    hist = mat[:, :o]; elig = np.flatnonzero((hist > 0).sum(1) >= 4)
    m0 = fit(o - 1, False); m1 = fit(o - 1, True)
    cf = [classical_forecasts(hist[i]) for i in elig]
    for h in range(1, MAX_H + 1):
        if o + h - 1 >= n_w: break
        X0 = ml_features(mat, o, h); X1 = np.column_stack([X0, price_feats(o, h)])
        p0 = np.clip(m0.predict(X0[elig]), 0, None); p1 = np.clip(m1.predict(X1[elig]), 0, None)
        for k, i in enumerate(elig):
            rows.append({"origin": o, "h": h, "StockCode": codes[i], "actual": mat[i, o + h - 1], "lgbm_no_price": p0[k], "lgbm_price": p1[k], "ses": cf[k]["ses"],
                         "price_change_target": price_feats(o, h)[i, 0]})
bt = pd.DataFrame(rows)
res = {"overall": {m: forecast_metrics(bt["actual"], bt[m]) for m in ("ses", "lgbm_no_price", "lgbm_price")}}
chg = bt["price_change_target"].abs() > 0.05
res["on_weeks_with_price_change_gt5pct"] = {m: forecast_metrics(bt.loc[chg, "actual"], bt.loc[chg, m]) for m in ("ses", "lgbm_no_price", "lgbm_price")}
res["share_of_cases_with_price_change_gt5pct"] = float(chg.mean())
# paired bootstrap over products: is the MAE gain vs SES distinguishable from noise?
ae = bt.assign(d=(bt["ses"] - bt["actual"]).abs() - (bt["lgbm_price"] - bt["actual"]).abs()).groupby("StockCode")["d"].mean()
rng = np.random.default_rng(SEED); bs = [rng.choice(ae.to_numpy(), len(ae)).mean() for _ in range(2000)]
res["mae_gain_vs_ses_per_case"] = {"mean": float(ae.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
res["decision"] = "price-aware model adopted ONLY for price-conditional scenario forecasts (planned price known); SES remains the default unconditional forecast" if res["overall"]["lgbm_price"]["MAE"] < min(res["overall"]["ses"]["MAE"], res["overall"]["lgbm_no_price"]["MAE"]) * 0.98 else "price-aware model NOT adopted: no measurable improvement over existing validated methods"
(REPORT_DIR / "retail" / "forecast_price_aware_results.json").write_text(json.dumps(res, indent=2))
for k in ("overall", "on_weeks_with_price_change_gt5pct"):
    print(k); [print(f"  {m:14s} MAE {v['MAE']:.3f} WAPE {v['WAPE']:.3f} bias {v['bias']:+.3f}") for m, v in res[k].items()]
print(res["share_of_cases_with_price_change_gt5pct"], res["decision"])

from trexo.ml.registry.registry import save_model_bundle
final = fit(n_w - 1, True)
meta = save_model_bundle("forecasting_price", {"lightgbm_price": final}, {"features": ML_FEATURE_NAMES + ["rel_log_price_target", "log_price_change_last_week", "rel_log_price_last_vs_mean8"],
        "validation": res, "usage": "requires the PLANNED price for the target week; do not use as an unconditional forecaster", "random_seed": SEED, "weeks_in_training": n_w})
print(meta["model_version"], res["mae_gain_vs_ses_per_case"])
