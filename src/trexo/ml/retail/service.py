"""Retail intelligence service: validated requests -> structured, explained RECOMMENDATIONS (never actions).
Extends (does not replace) trexo.ml.inference.service.InferenceService."""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
from ..dead_stock.classifier import _load_rule_curve, rule_score
from ..registry.registry import load_model_bundle
from ..inference.service import InvalidRequestError, ModelUnavailableError
from .inventory.ledger import process_ledger, reconcile
from .ageing.engine import stock_age_table, classify_stock, selling_queue, AgeingConfig, ageing_distribution
from .pricing.scenarios import scenario_table, choose_offer, PricingRules
from .recovery.engine import recovery_plan

DISCLAIMER = "Recommendation only. No price change, discount, purchase or transfer is executed; requires authorised business approval."


class RetailIntelligenceService:
    def __init__(self):
        try:
            self.curve = _load_rule_curve()
            self.pricing_objs, self.pricing_meta = load_model_bundle("pricing")
            self.bundle_objs, self.bundle_meta = load_model_bundle("bundles")
        except FileNotFoundError as e:
            raise ModelUnavailableError(str(e)) from e
        self.el = self.pricing_objs["elasticity"]

    def _elasticity(self, req):
        if req.get("elasticity") is not None:
            e = float(req["elasticity"]); 
            if e > 0: raise InvalidRequestError("elasticity must be <= 0")
            return e, "assumed (caller supplied)"
        if self.el["usable_as_pooled_prior"]:
            return (self.el["conservative"] if req.get("conservative", True) else self.el["central"]), "estimated_pooled (associational, observational)"
        return -1.0, "assumed (no validated estimate)"

    def _ledger(self, events, as_of):
        if not isinstance(events, list) or not events: raise InvalidRequestError("events must be a non-empty list")
        r = process_ledger(pd.DataFrame(events))
        return r, pd.Timestamp(as_of) if as_of else r.accepted["ts"].max()

    def inventory_balances(self, req: dict) -> dict:
        r, as_of = self._ledger(req.get("events"), req.get("as_of"))
        out = {"status": "OK", "as_of": str(as_of.date()), "balances": r.balances.to_dict("records"), "rejected_events": r.rejected[["event_id", "reject_reason"]].to_dict("records"),
               "warnings": [f"{len(r.rejected)} event(s) rejected; stock excludes them"] if len(r.rejected) else [], "disclaimer": DISCLAIMER}
        if req.get("reported_counts"): out["reconciliation"] = reconcile(r.balances, pd.DataFrame(req["reported_counts"])).to_dict("records")
        return out

    def stock_priority(self, req: dict) -> dict:
        r, as_of = self._ledger(req.get("events"), req.get("as_of"))
        acc = r.accepted; sales = acc[(acc["type"] == "SALE") & (acc["ts"] <= as_of)]
        age = stock_age_table(r.layers, as_of)
        last = sales.groupby("product_id")["ts"].max()
        win = int(req.get("velocity_window_days", 56)); recent = sales[sales["ts"] > as_of - pd.Timedelta(days=win)].groupby("product_id")["qty"].sum() / win
        dsl = (as_of - age["product_id"].map(last)).dt.days
        risk = rule_score(dsl.fillna(10 ** 4).to_numpy(float), self.curve); risk = np.where(dsl.isna(), np.nan, risk)
        dem = pd.DataFrame({"product_id": age["product_id"], "forecast_daily": age["product_id"].map(recent).fillna(0.0).to_numpy(), "risk_score": risk, "days_since_last_sale": dsl.to_numpy()})
        cfg = AgeingConfig(**req.get("ageing_config", {}))
        c = classify_stock(age, dem, cfg); q = selling_queue(c)
        warn = []
        if (c["category"] == "Confirmed Dead Stock").any(): warn.append("Confirmed Dead Stock = ledger-verified stock + critical demand risk + no sale for the configured days")
        if age["cost_known_share"].lt(1).any(): warn.append("some stock layers have no unit cost: capital exposure unknown for those products")
        warn.append("ageing thresholds are configuration defaults, not calibrated on real inventory")
        return {"status": "OK", "as_of": str(as_of.date()), "queue": q.drop(columns=["capital_exposure_known_part"], errors="ignore").to_dict("records"),
                "ageing_distribution_units": ageing_distribution(r.layers, as_of).to_dict("records"), "warnings": warn, "disclaimer": DISCLAIMER}

    def pricing_scenarios(self, req: dict) -> dict:
        for k in ("price", "stock", "daily_demand"):
            if req.get(k) is None: raise InvalidRequestError(f"{k} is required")
        e, src = self._elasticity(req)
        rules = PricingRules(**req.get("rules", {}))
        t = scenario_table(float(req["price"]), float(req["stock"]), float(req["daily_demand"]), int(req.get("horizon_days", 28)), e, src,
                           None if req.get("cost") is None else float(req["cost"]), rules, holding_rate_annual=req.get("holding_rate_annual"),
                           obsolescence_rate=float(req.get("obsolescence_rate", 0.0)))
        sel = choose_offer(t, rules)
        warn = ["demand response is modelled from an observational, associational elasticity (not causal); validate with a controlled offer test"]
        if req.get("cost") is None: warn.append("cost missing: profit not computed, no offer selected")
        return {"status": "OK", "scenarios": t.to_dict("records"), "selection": sel, "elasticity_used": e, "elasticity_source": src, "warnings": warn, "disclaimer": DISCLAIMER}

    def bundle_recommendations(self, req: dict) -> dict:
        pid = req.get("product_id")
        if not pid: raise InvalidRequestError("product_id required")
        d = self.bundle_objs["rules_directed"]; d = d[(d["consequent"] == pid) & (d["lift"] >= float(req.get("min_lift", 1.5))) & (d["confidence"] >= float(req.get("min_conf", 0.05)))]
        d = d.assign(rank_score=d["lift"] * d["confidence"] * np.log1p(d["pair_baskets"])).sort_values("rank_score", ascending=False).head(int(req.get("top_k", 3)))
        return {"status": "OK", "product_id": pid, "candidates": d.to_dict("records"),
                "warnings": ["co-purchase association only; bundle economics need prices and costs; no causal uplift claimed"] + ([] if len(d) else ["no co-purchase evidence: no bundle recommended"]), "disclaimer": DISCLAIMER}

    def recovery_recommendations(self, req: dict) -> dict:
        sq = self.stock_priority(req)
        if not sq["queue"]: return {"status": "OK", "plan": [], "warnings": sq["warnings"], "disclaimer": DISCLAIMER}
        r, as_of = self._ledger(req.get("events"), req.get("as_of"))
        age = stock_age_table(r.layers, as_of); acc = r.accepted
        sale = acc[acc["type"] == "SALE"]; price = (sale.dropna(subset=["unit_price"]).sort_values("ts").groupby("product_id")["unit_price"].last())
        price = price.combine_first(pd.Series(req.get("prices", {}), dtype=float))
        cost = pd.Series(req.get("costs", {}), dtype=float) if req.get("costs") else None
        e, src = self._elasticity(req); stock = pd.DataFrame(sq["queue"])
        plan = recovery_plan(stock, price, cost, elasticity=e, elasticity_source="estimated_pooled" if "estimated" in src else "assumed",
                             rules=PricingRules(**req.get("rules", {})), holding_rate_annual=req.get("holding_rate_annual"))
        return {"status": "OK", "plan": plan.to_dict("records"), "elasticity_source": src, "warnings": sq["warnings"], "disclaimer": DISCLAIMER}
