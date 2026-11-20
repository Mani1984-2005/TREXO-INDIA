"""Stock ageing + selling-priority engine (works ONLY on verified ledger output).

Categories (all thresholds configurable, defaults are NOT calibrated on real inventory -
no operational data exists yet; they must be calibrated on pilot data):
  Fresh      : weighted stock age <= fresh_days
  Normal     : coverage <= normal_cover_days and not older than ageing_days
  Ageing     : weighted age > ageing_days OR oldest layer > 2*ageing_days with coverage > normal_cover
  Slow       : coverage > slow_cover_days (stock would take > N days to sell at forecast demand)
  At-Risk / Critical : demand-inactivity risk score (existing calibrated rule) combined with stock held
  Confirmed Dead Stock: stock > 0 AND demand risk >= critical AND no sale for >= dead_days AND ledger-verified
Priority points (documented): urgency = 0.35*risk + 0.25*age_factor + 0.25*coverage_factor + 0.15*expiry_factor,
then x value weight (capital exposure rank, only when cost known).
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass
class AgeingConfig:
    fresh_days: float = 30
    ageing_days: float = 90
    normal_cover_days: float = 60
    slow_cover_days: float = 180
    atrisk_score: float = 0.6
    critical_score: float = 0.8
    confirmed_dead_days: float = 90
    expiry_warn_days: float = 30
    w_risk: float = 0.35; w_age: float = 0.25; w_cover: float = 0.25; w_expiry: float = 0.15


CATS = ["Fresh Stock", "Normal Stock", "Ageing Stock", "Slow-Moving Stock", "At-Risk Stock",
        "Critical Dead-Stock Risk", "Confirmed Dead Stock"]


def stock_age_table(layers: pd.DataFrame, as_of) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    l = layers.copy(); l["age_days"] = (as_of - pd.to_datetime(l["received_ts"])).dt.days.clip(lower=0)
    l["value"] = l["qty_remaining"] * l["unit_cost"]
    l["exp_days"] = (pd.to_datetime(l["expiry_date"]) - as_of).dt.days
    g = l.groupby("product_id")
    t = pd.DataFrame({
        "units_on_hand": g["qty_remaining"].sum(),
        "weighted_age_days": g.apply(lambda x: np.average(x["age_days"], weights=x["qty_remaining"]), include_groups=False),
        "oldest_layer_age_days": g["age_days"].max(),
        "capital_exposure": g["value"].sum(min_count=1),       # NaN when ANY layer lacks cost -> unknown, not zero
        "cost_known_share": g.apply(lambda x: x.loc[x["unit_cost"].notna(), "qty_remaining"].sum() / x["qty_remaining"].sum(), include_groups=False),
        "units_expiring_soon": g.apply(lambda x: x.loc[x["exp_days"].le(30) & x["exp_days"].notna(), "qty_remaining"].sum(), include_groups=False),
        "min_days_to_expiry": g["exp_days"].min(),
    })
    capital_partial = g.apply(lambda x: (x["qty_remaining"] * x["unit_cost"]).sum(), include_groups=False)
    t["capital_exposure_known_part"] = capital_partial
    return t.reset_index()


def ageing_distribution(layers: pd.DataFrame, as_of, edges=(30, 60, 90, 180)) -> pd.DataFrame:
    a = (pd.Timestamp(as_of) - pd.to_datetime(layers["received_ts"])).dt.days.clip(lower=0)
    b = pd.cut(a, [-1, *edges, 10 ** 6], labels=[f"0-{edges[0]}"] + [f"{edges[i]+1}-{edges[i+1]}" for i in range(len(edges) - 1)] + [f">{edges[-1]}"])
    return layers.assign(bucket=b).groupby("bucket", observed=False)["qty_remaining"].sum().reset_index(name="units")


def classify_stock(age: pd.DataFrame, demand: pd.DataFrame, cfg: AgeingConfig = AgeingConfig()) -> pd.DataFrame:
    """demand columns: product_id, forecast_daily (units/day), risk_score (existing calibrated 0-1 or NaN),
    days_since_last_sale (NaN if never), recent_velocity_daily."""
    d = age.merge(demand, on="product_id", how="left")
    d["coverage_days"] = np.where(d["forecast_daily"] > 0, d["units_on_hand"] / d["forecast_daily"], np.inf)
    d["demand_evidence_available"] = d["risk_score"].notna()
    cat = []
    for r in d.itertuples():
        rs = r.risk_score if pd.notna(r.risk_score) else np.nan
        if r.units_on_hand <= 0: cat.append(None); continue
        if pd.notna(rs) and rs >= cfg.critical_score and pd.notna(r.days_since_last_sale) and r.days_since_last_sale >= cfg.confirmed_dead_days:
            cat.append("Confirmed Dead Stock")
        elif pd.notna(rs) and rs >= cfg.critical_score: cat.append("Critical Dead-Stock Risk")
        elif pd.notna(rs) and rs >= cfg.atrisk_score: cat.append("At-Risk Stock")
        elif r.coverage_days > cfg.slow_cover_days: cat.append("Slow-Moving Stock")
        elif r.weighted_age_days > cfg.ageing_days or (r.oldest_layer_age_days > 2 * cfg.ageing_days and r.coverage_days > cfg.normal_cover_days):
            cat.append("Ageing Stock")
        elif r.weighted_age_days <= cfg.fresh_days: cat.append("Fresh Stock")
        else: cat.append("Normal Stock")
    d["category"] = cat
    d = d[d["category"].notna()].copy()
    age_f = (d["weighted_age_days"] / (2 * cfg.ageing_days)).clip(0, 1)
    cov_f = (d["coverage_days"].replace(np.inf, 10 * cfg.slow_cover_days) / (2 * cfg.slow_cover_days)).clip(0, 1)
    exp_f = np.where(d["min_days_to_expiry"].notna(), (1 - d["min_days_to_expiry"].clip(0, cfg.expiry_warn_days * 2) / (cfg.expiry_warn_days * 2)), 0.0)
    risk_f = d["risk_score"].fillna(0.0)
    d["urgency"] = cfg.w_risk * risk_f + cfg.w_age * age_f + cfg.w_cover * cov_f + cfg.w_expiry * exp_f
    d["value_weight"] = 1.0
    known = d["capital_exposure"].notna()
    if known.sum() >= 3:
        d.loc[known, "value_weight"] = 0.5 + 0.5 * d.loc[known, "capital_exposure"].rank(pct=True)
    d["priority_points"] = d["urgency"] * d["value_weight"]
    d["priority"] = np.where(d["priority_points"] >= 0.6, "P1", np.where(d["priority_points"] >= 0.4, "P2", np.where(d["priority_points"] >= 0.2, "P3", "P4")))
    return d


def selling_queue(c: pd.DataFrame, names: pd.Series | None = None) -> pd.DataFrame:
    """Only products that genuinely warrant earlier selling: not Fresh/Normal with healthy coverage."""
    q = c[~c["category"].isin(["Fresh Stock", "Normal Stock"])].copy()
    q["why_sell_early"] = q.apply(lambda r: "; ".join(filter(None, [
        f"{r['category']}",
        f"weighted stock age {r['weighted_age_days']:.0f} days (oldest layer {r['oldest_layer_age_days']:.0f})",
        f"{r['units_on_hand']:.0f} units remain = {'no forecast demand' if np.isinf(r['coverage_days']) else str(round(r['coverage_days'])) + ' days of cover'}",
        (f"demand-inactivity risk {r['risk_score']:.0%}" if pd.notna(r["risk_score"]) else "no demand-risk evidence"),
        (f"{r['units_expiring_soon']:.0f} units expire within 30 days" if r["units_expiring_soon"] > 0 else "")])), axis=1)
    q["urgency_label"] = q["priority"].map({"P1": "Immediate", "P2": "This week", "P3": "This month", "P4": "Monitor"})
    q["expected_demand_note"] = q["forecast_daily"].apply(lambda x: f"~{x * 7:.1f} units/week forecast" if pd.notna(x) else "no forecast")
    q = q.sort_values("priority_points", ascending=False).reset_index(drop=True)
    q.insert(0, "queue_rank", range(1, len(q) + 1))
    return q
