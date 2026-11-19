"""Train + compare dead-stock risk models with chronological validation. Writes artifacts."""
import json, sys, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, joblib
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score
from trexo.ml.config import *
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.features.labels import build_training_table
from trexo.ml.validation.splits import make_cutoffs, forward_chain_folds
from trexo.ml.dead_stock import calibration as cal
from trexo.ml.dead_stock.model import *
from trexo.ml.evaluation.classification import best_threshold_fbeta, evaluate_binary, calibration_table
from trexo.ml.registry.registry import save_model_bundle, data_fingerprint, feature_schema_fingerprint

np.random.seed(SEED)
H = HorizonConfig(); t0 = time.time()
sales = load_sales(); c = make_cutoffs(sales["Date"].min(), H)
tab = {k: build_training_table(sales, v if isinstance(v, list) else [v], H.label_horizon_days)
       for k, v in c.items()}
tr, va, te = tab["train"], tab["val"], tab["test"]
print("rows train/val/test:", len(tr), len(va), len(te))
X = lambda d: d[MODEL_FEATURES]

# ---- baseline + rule score (train-only isotonic on recency) -----------------
iso = cal.fit_rule_score(tr)
base_val, base_te = iso.predict(va["days_since_last_sale"]), iso.predict(te["days_since_last_sale"])
results = {"cutoffs": {k: [str(x.date()) for x in v] if isinstance(v, list) else str(v.date()) for k, v in c.items()},
           "horizon_days": H.label_horizon_days, "models": {}}
thr_b = best_threshold_fbeta(va["y_inactive"], base_val)
results["models"]["baseline_recency_rule"] = {"val": evaluate_binary(va["y_inactive"], base_val, thr_b),
                                              "test": evaluate_binary(te["y_inactive"], base_te, thr_b)}
prev = np.full(len(te), tr["y_inactive"].mean())
results["prevalence_prior_test_pr_auc"] = float(average_precision_score(te["y_inactive"], prev))

# ---- tuning by purged forward-chaining CV inside the training period --------
folds = forward_chain_folds(c["train"], H.label_horizon_days)
cands = candidates(); lg = lightgbm_candidate()
if lg: cands["lightgbm"] = lg
fitted = {}
for name, (est, grid) in cands.items():
    best, best_s = None, -1
    for params in grid:
        sc = []
        for trc, v in folds:
            a = tr[tr["cutoff"].isin(trc)]; b = tr[tr["cutoff"] == v]
            m = with_params(est, params).fit(X(a), a["y_inactive"])
            sc.append(average_precision_score(b["y_inactive"], m.predict_proba(X(b))[:, 1]))
        if np.mean(sc) > best_s: best, best_s = params, float(np.mean(sc))
    m = with_params(est, best).fit(X(tr), tr["y_inactive"])
    pv = m.predict_proba(X(va))[:, 1]; pt = m.predict_proba(X(te))[:, 1]
    ptr = m.predict_proba(X(tr))[:, 1]
    thr = best_threshold_fbeta(va["y_inactive"], pv)
    results["models"][name] = {"best_params": best, "cv_pr_auc": best_s,
        "train_pr_auc": float(average_precision_score(tr["y_inactive"], ptr)),
        "val": evaluate_binary(va["y_inactive"], pv, thr), "test": evaluate_binary(te["y_inactive"], pt, thr)}
    fitted[name] = (m, best, thr)
    print(name, best, "val PR-AUC %.3f test PR-AUC %.3f" % (results["models"][name]["val"]["pr_auc"], results["models"][name]["test"]["pr_auc"]))

# ---- model selection: validation PR-AUC; acceptance vs baseline ------------
bv = results["models"]["baseline_recency_rule"]["val"]["pr_auc"]
bt = results["models"]["baseline_recency_rule"]["test"]["pr_auc"]
ranked = sorted(fitted, key=lambda n: -results["models"][n]["val"]["pr_auc"])
sel = ranked[0]
r = results["models"][sel]
MARGIN = 0.02   # required PR-AUC improvement over the recency rule on BOTH val and test
accepted = (r["val"]["pr_auc"] - bv >= MARGIN) and (r["test"]["pr_auc"] - bt >= MARGIN) \
           and r["test"]["brier"] < r["test"]["brier_prevalence_baseline"]
results["selection"] = {"criterion": "highest validation PR-AUC", "selected": sel, "ranked": ranked,
    "acceptance_rule": f"PR-AUC >= baseline+{MARGIN} on val AND test, and Brier < prevalence-prior Brier",
    "accepted_over_baseline": bool(accepted)}
print("selected", sel, "accepted:", accepted)

# ---- stability: seed sensitivity of selected config on test PR-AUC ----------
est_sel, params_sel, thr_sel = fitted[sel]
stab = []
for seed in (1, 2, 3, 4, 5):
    m = with_params(cands[sel][0], params_sel)
    if "random_state" in m.get_params(): m.set_params(random_state=seed)
    m.fit(X(tr), tr["y_inactive"]); stab.append(average_precision_score(te["y_inactive"], m.predict_proba(X(te))[:, 1]))
results["stability_test_pr_auc_over_seeds"] = {"mean": float(np.mean(stab)), "std": float(np.std(stab))}

# ---- permutation importance on test (explainability, model-agnostic) -------
from sklearn.inspection import permutation_importance
pi = permutation_importance(est_sel, X(te), te["y_inactive"], scoring="average_precision",
                            n_repeats=5, random_state=SEED)
imp = pd.DataFrame({"feature": MODEL_FEATURES, "importance": pi.importances_mean, "std": pi.importances_std}) \
        .sort_values("importance", ascending=False)
imp.to_csv(REPORT_DIR / "dead_stock_permutation_importance.csv", index=False)
results["top_features"] = imp.head(8)["feature"].tolist()

# ---- calibration of selected model on validation (isotonic), tested on test -
pv = est_sel.predict_proba(X(va))[:, 1]; pt = est_sel.predict_proba(X(te))[:, 1]
ciso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(pv, va["y_inactive"])
pt_c = ciso.predict(pt)
thr_c = best_threshold_fbeta(va["y_inactive"], ciso.predict(pv))
results["calibration"] = {"raw_test_ece": results["models"][sel]["test"]["ece"],
                          "calibrated_test": evaluate_binary(te["y_inactive"], pt_c, thr_c)}
calibration_table(te["y_inactive"], pt).to_csv(REPORT_DIR / "dead_stock_calibration_raw_test.csv", index=False)
calibration_table(te["y_inactive"], pt_c).to_csv(REPORT_DIR / "dead_stock_calibration_isotonic_test.csv", index=False)

# ---- PSI feature drift train vs test ---------------------------------------
def psi(a, b, bins=10):
    q = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    if len(q) < 3: return 0.0
    pa = np.histogram(a, q)[0] / len(a) + 1e-6; pb = np.histogram(np.clip(b, q[0], q[-1]), q)[0] / len(b) + 1e-6
    return float(((pa - pb) * np.log(pa / pb)).sum())
drift = pd.DataFrame({"feature": MODEL_FEATURES,
                      "psi_train_vs_test": [psi(tr[f].to_numpy(float), te[f].to_numpy(float)) for f in MODEL_FEATURES]}) \
          .sort_values("psi_train_vs_test", ascending=False)
drift.to_csv(REPORT_DIR / "dead_stock_feature_drift_psi.csv", index=False)
results["max_feature_psi"] = float(drift["psi_train_vs_test"].max())

# ---- production artifacts: refit on ALL labelled cutoffs (<= test cutoff) ---
all_cut = c["train"] + [c["val"], c["test"]]
allt = pd.concat([tr, va, te], ignore_index=True)
iso_full = cal.fit_rule_score(allt)
edges = [0.2, 0.4, 0.6, 0.8]
bands = {"val": cal.band_table(va.assign(rs=iso.predict(va["days_since_last_sale"])), "rs", edges),
         "test": cal.band_table(te.assign(rs=iso.predict(te["days_since_last_sale"])), "rs", edges)}
for k, v in bands.items(): v.to_csv(REPORT_DIR / f"rule_score_band_validation_{k}.csv", index=False)
cal.save_calibration(iso_full, edges, {
    "recency_days_at_probability": {str(p): cal.recency_for_probability(iso_full, p) for p in (.2, .4, .6, .8)},
    "train_max_recency_days": int(allt["days_since_last_sale"].max()),
    "fit_cutoffs": [str(x.date()) for x in all_cut], "horizon_days": H.label_horizon_days})
final = with_params(cands[sel][0], params_sel).fit(allt[MODEL_FEATURES], allt["y_inactive"])
# calibrator for the deployable model: out-of-time predictions only (val+test cutoffs from the train-only model)
ciso_full = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(
    np.r_[pv, pt], np.r_[va["y_inactive"], te["y_inactive"]])
results["trained_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
results["runtime_seconds"] = round(time.time() - t0, 1)
meta = save_model_bundle("dead_stock", {"estimator": final, "calibrator": ciso_full, "rule_calibrator": iso_full},
    {"model_name": sel, "challenger_model": sel,
     "deployed_predictor": sel if accepted else "baseline_recency_rule",
     "deployment_note": ("ML challenger accepted" if accepted else
        "ML challenger REJECTED (no sufficient improvement over the calibrated recency rule); "
        "inference uses the calibrated recency rule; estimator kept for audit/comparison only"),
     "params": params_sel, "features": MODEL_FEATURES, "threshold_calibrated": thr_c,
     "target": f"no valid sale in next {H.label_horizon_days} days (demand inactivity; NOT physical dead stock)",
     "accepted_over_baseline": bool(accepted), "metrics_test_train_only_model": results["models"][sel]["test"],
     "calibrated_test": results["calibration"]["calibrated_test"], "fit_cutoffs": [str(x.date()) for x in all_cut],
     "random_seed": SEED, "label_horizon_days": H.label_horizon_days,
     "feature_schema": MODEL_FEATURES,
     "feature_schema_sha256": feature_schema_fingerprint(MODEL_FEATURES),
     "training_data_fingerprint": data_fingerprint([ML_DATA_DIR / "valid_sales_v1.csv.gz",
                                                    ML_DATA_DIR / "data_manifest_v1.json"]),
     "feature_ranges": {f: [float(allt[f].min()), float(allt[f].max())] for f in MODEL_FEATURES}})
results["training_data_fingerprint"] = meta.get("training_data_fingerprint")
results["artifact"] = meta
(REPORT_DIR / "dead_stock_model_results.json").write_text(json.dumps(results, indent=2, default=str))
print("done in", results["runtime_seconds"], "s")
