"""Inference service: validated single-product requests -> structured, explained results.
Never fabricates: no valid sales -> no prediction; missing artifact -> ModelUnavailableError."""
from __future__ import annotations
import datetime as dt
import json
import numpy as np
import pandas as pd
from ..config import (REPORT_DIR, ClassificationThresholds, load_calibrated_thresholds,
                      SCHEMA_VERSION, NON_PRODUCT_CODES, D01_BAD_DEBT_INVOICES,
                      D01_EXCLUSION_REASON)
from ..features.product_features import build_features
from ..dead_stock.classifier import classify_products, _load_rule_curve, rule_score, classify_score
from ..forecasting.engine import classical_forecasts, demand_class, ml_features, MAX_H
from ..movement.movement import abc_class, xyz_class
from ..recommendations.engine import build_queue, VALUE_W, EVID_W, tier
from ..reorder.policy import reorder_calc, demand_based_guidance
from ..explainability.explain import five_part_explanation
from ..anomaly.detector import transaction_quality
from ..registry.registry import load_model_bundle


class ModelUnavailableError(RuntimeError):
    pass


class InvalidRequestError(ValueError):
    pass


def validate_request(req: dict) -> tuple[pd.DataFrame, list[str], pd.Timestamp]:
    """Returns (valid sales frame, warnings, as_of). Invalid records are counted, never silently dropped."""
    if not isinstance(req, dict): raise InvalidRequestError("request must be an object")
    pid = req.get("product_id")
    if not isinstance(pid, str) or not pid.strip(): raise InvalidRequestError("product_id is required (non-empty string)")
    pid = pid.strip()
    if pid.upper() in {str(c).upper() for c in NON_PRODUCT_CODES}:
        raise InvalidRequestError(f"'{pid}' is a non-product StockCode and cannot receive a product-demand prediction")
    hist = req.get("sales_history")
    if not isinstance(hist, list): raise InvalidRequestError("sales_history must be a list of records")
    if req.get("as_of"):
        try:
            as_of_req = pd.Timestamp(req["as_of"]).normalize()
            if pd.isna(as_of_req): raise ValueError
        except Exception as e:
            raise InvalidRequestError("as_of must be a valid date") from e
    else:
        as_of_req = None
    warnings: list[str] = []
    rows, bad = [], {"missing_or_invalid_date": 0, "non_numeric": 0, "non_positive_quantity": 0,
                     "non_positive_price": 0, "d01_governance_excluded": 0}
    for r in hist:
        if not isinstance(r, dict):
            bad["non_numeric"] += 1; continue
        inv = str(r.get("invoice_no", ""))
        if inv.strip() in D01_BAD_DEBT_INVOICES:
            bad["d01_governance_excluded"] += 1; continue
        try:
            d = pd.Timestamp(r.get("date")).normalize()
            if pd.isna(d): raise ValueError
        except Exception:
            bad["missing_or_invalid_date"] += 1; continue
        try:
            q = float(r.get("quantity")); p = float(r.get("unit_price"))
        except (TypeError, ValueError):
            bad["non_numeric"] += 1; continue
        if not np.isfinite(q) or not np.isfinite(p): bad["non_numeric"] += 1; continue
        if q <= 0: bad["non_positive_quantity"] += 1; continue
        if p <= 0: bad["non_positive_price"] += 1; continue
        if as_of_req is not None and d > as_of_req:
            bad["future_dated"] = bad.get("future_dated", 0) + 1
            continue
        cid = r.get("customer_id")
        try:
            cid_val = float(cid) if cid not in (None, "") else np.nan
        except (TypeError, ValueError):
            cid_val = np.nan
        rows.append({"SourceRow": len(rows), "InvoiceNo": str(r.get("invoice_no", f"auto{len(rows)}")), "StockCode": pid,
                     "Description": req.get("description"), "Quantity": q, "UnitPrice": p, "LineValue": q * p,
                     "Date": d, "InvoiceDate": d, "CustomerID": cid_val,
                     "Country": r.get("country"), "IsExactDuplicate": False})
    for k, v in bad.items():
        if v:
            msg = f"{v} record(s) excluded: {k.replace('_', ' ')} (not deleted from caller's data)"
            if k == "d01_governance_excluded":
                msg = (f"{v} record(s) excluded by governance decision {D01_EXCLUSION_REASON}: "
                       "bad-debt financial event is not product demand")
            warnings.append(msg)
    sales = pd.DataFrame(rows)
    if len(sales) and sales.duplicated(["InvoiceNo", "Quantity", "UnitPrice", "Date"]).any():
        warnings.append("possible duplicate sale records present (retained)")
    as_of = as_of_req if as_of_req is not None else (sales["Date"].max() if len(sales) else pd.NaT)
    if len(sales) and not pd.isna(as_of) and (sales["Date"] > as_of).any():
        warnings.append("records dated after as_of were ignored for all features")
        sales = sales[sales["Date"] <= as_of]
    return sales, warnings, as_of


class InferenceService:
    def __init__(self):
        try:
            self.curve = _load_rule_curve()
        except FileNotFoundError as e:
            raise ModelUnavailableError("calibration.json missing: run scripts/ml_train_dead_stock.py") from e
        try:
            self.ds_objs, self.ds_meta = load_model_bundle("dead_stock")
            self.fc_objs, self.fc_meta = load_model_bundle("forecasting")
            self.mv_objs, self.mv_meta = load_model_bundle("movement")
        except FileNotFoundError as e:
            raise ModelUnavailableError(str(e)) from e
        self.t = load_calibrated_thresholds()

    # ---- helpers -------------------------------------------------------------
    def _base(self, req):
        sales, warnings, as_of = validate_request(req)
        pid = req["product_id"].strip()
        out = {"schema_version": SCHEMA_VERSION, "product_id": pid,
               "request_id": req.get("request_id"),
               "prediction_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
               "as_of": None if pd.isna(as_of) else str(as_of.date()), "warnings": warnings,
               "missing_input_warnings": []}
        for k in ("on_hand_qty", "unit_cost", "lead_time_days", "supplier_terms", "lifecycle_status"):
            if req.get(k) is None: out["missing_input_warnings"].append(f"{k} not supplied")
        for k in ("on_hand_qty", "on_order_qty", "lead_time_days", "lead_time_sd_days"):
            if req.get(k) is not None:
                try:
                    v = float(req[k])
                except (TypeError, ValueError) as e:
                    raise InvalidRequestError(f"{k} must be numeric") from e
                if not np.isfinite(v) or v < 0:
                    raise InvalidRequestError(f"{k} must be a finite value >= 0")
        if req.get("moq") is not None and (not np.isfinite(float(req["moq"])) or float(req["moq"]) <= 0):
            raise InvalidRequestError("moq must be > 0")
        if req.get("service_level") is not None and not 0.5 <= float(req["service_level"]) < 1:
            raise InvalidRequestError("service_level must be in [0.5, 1)")
        if sales.empty:
            out.update(status="NO_VALID_SALES", prediction=None,
                       explanation="No valid sales records: no demand-based prediction is made (absence of sales history "
                                   "is not evidence of dead stock).", model_version=None)
            return None, sales, out
        feat = build_features(sales, as_of, data_start=sales["Date"].min())
        feat["history_days"] = (as_of - sales["Date"].min()).days
        return feat, sales, out

    def _metadata(self, meta: dict) -> dict:
        return {"model_version": meta.get("model_version"),
                "model_trained_at_utc": meta.get("trained_at_utc"),
                "pipeline_version": meta.get("pipeline_version")}

    def _classified(self, feat, sales, req):
        oh = None
        if req.get("on_hand_qty") is not None:
            if float(req["on_hand_qty"]) < 0: raise InvalidRequestError("on_hand_qty must be >= 0")
            oh = pd.DataFrame({"StockCode": feat["StockCode"], "on_hand_qty": [float(req["on_hand_qty"])]})
        desc = pd.DataFrame({"StockCode": feat["StockCode"], "Description": [req.get("description")]})
        return classify_products(feat, sales, desc, on_hand=oh, curve=self.curve, thresholds=self.t).iloc[0]

    # ---- public API ----------------------------------------------------------
    def dead_stock_detection(self, req: dict) -> dict:
        feat, sales, out = self._base(req)
        if feat is None: return out
        c = self._classified(feat, sales, req)
        out.update(status="OK", **self._metadata(self.ds_meta),
                   predictor=self.ds_meta["deployed_predictor"],
                   classification=c["classification"], dead_stock_risk_score=float(c["dead_stock_risk_score"]),
                   prediction={"p_no_sale_next_60d": float(c["dead_stock_risk_score"])},
                   days_since_last_sale=int(c["days_since_last_sale"]), historical_sales_quantity=float(c["total_qty"]),
                   sales_velocity_units_per_day=float(c["velocity_per_day"]), demand_pattern=c["demand_pattern"],
                   evidence_quality=c["evidence_quality"], evidence_flags=c["evidence_flags"],
                   evidence_basis=c["evidence_basis"], stock_verification_required=bool(c["stock_verification_required"]),
                   inventory_value_available=bool(c["inventory_value_available"]),
                   human_review_required=bool(c["human_review_required"]),
                   confidence={"evidence_quality": c["evidence_quality"],
                               "note": "probability is an empirical calibration (isotonic) of 60-day inactivity vs recency"},
                   supporting_metrics={k: float(c[k]) for k in ("qty_30d", "qty_90d", "n_invoices", "mean_gap_days", "trend_ratio_60")},
                   explanation=c["risk_explanation"], recommended_action=c["recommended_intervention"],
                   status_type=c["status_type"])
        return out

    def dead_stock_risk_prediction(self, req: dict) -> dict:
        return self.dead_stock_detection(req)   # deployed predictor == calibrated rule (ML challenger rejected)

    def demand_forecast(self, req: dict, horizon_weeks: int = 4) -> dict:
        if not 1 <= horizon_weeks <= MAX_H: raise InvalidRequestError(f"horizon_weeks must be 1..{MAX_H}")
        feat, sales, out = self._base(req)
        if feat is None: return out
        as_of = pd.Timestamp(out["as_of"])
        ages = ((as_of - sales["Date"]).dt.days // 7)
        n = int(ages.max()) + 1
        y = np.zeros(n)
        for a, q in zip(ages, sales["Quantity"]): y[n - 1 - a] += q       # last bin = most recent complete 7-day block
        active = int((y > 0).sum())
        cls = demand_class(y) if active >= self.fc_meta["min_active_weeks"] else "insufficient_history"
        method = self.fc_meta["selected_method_by_demand_class"].get(cls, self.fc_meta["fallback_method"])
        if method == "lightgbm":
            method = self.fc_meta["fallback_method"]  # single-series LightGBM needs the population panel; use fallback
        level = classical_forecasts(y)[method]
        out.update(status="OK", **self._metadata(self.fc_meta), method=method, demand_class=cls,
                   forecast_weekly_units=[float(level)] * horizon_weeks, forecast_total_units=float(level * horizon_weeks),
                   prediction={"expected_units_total": float(level * horizon_weeks)},
                   confidence={"active_weeks": active, "backtest_WAPE_overall_reference": self.fc_meta["overall_backtest"].get(method, {}).get("WAPE"),
                               "note": "level forecast; horizon > 8 weeks not supported by one year of data"},
                   explanation=f"{method.upper()} level over {n} weekly bins ({active} active); class {cls}.")
        if active < self.fc_meta["min_active_weeks"]:
            out["warnings"].append("fewer than 4 active weeks: fallback method (MA8) used; low reliability")
        return out

    def movement_classification(self, req: dict) -> dict:
        feat, sales, out = self._base(req)
        if feat is None: return out
        f = feat.iloc[0]; pop = self.mv_objs["population"]; t = self.t
        rev = float(sales["LineValue"].sum()); srt = pop["revenue_sorted_desc"]
        rank = int((srt > rev).sum()); share_before = srt[:rank].sum() / srt.sum()
        abc = "A" if share_before < t.abc_a_share else "B" if share_before < t.abc_b_share else "C"
        if f["days_since_last_sale"] > pop["dead_recency_days"]: speed = "Non-moving"
        elif f["velocity_per_day"] >= pop["velocity_q_fast"]: speed = "Fast-moving"
        elif f["velocity_per_day"] <= pop["velocity_q_slow"]: speed = "Slow-moving"
        else: speed = "Medium-moving"
        trend = "Declining" if f["trend_ratio_60"] <= t.trend_decline_ratio else "Growing" if f["trend_ratio_60"] >= t.trend_growth_ratio else "Stable"
        xyz = "X" if f["monthly_cv"] <= t.xyz_x_max_cv else "Y" if f["monthly_cv"] <= t.xyz_y_max_cv else "Z"
        out.update(status="OK", **self._metadata(self.mv_meta), speed_class=speed, abc_class=abc, xyz_class=xyz,
                   abc_xyz=abc + xyz, trend_class=trend, intermittent=bool(f["mean_gap_days"] > 21 or f["gap_cv"] > 1),
                   prediction={"speed_class": speed}, explanation="Rule-based classes using population statistics saved at training time; ABC uses historical sales revenue.",
                   confidence={"note": "ABC rank is relative to the training population"})
        return out

    def reorder_recommendation(self, req: dict) -> dict:
        d = self.demand_forecast(req, horizon_weeks=4)
        if d["status"] != "OK": return d
        det = self.dead_stock_detection(req)
        daily = d["forecast_total_units"] / 28.0
        feat, sales, _ = self._base(req)
        dsd = float(sales.groupby("Date")["Quantity"].sum().reindex(
            pd.date_range(sales["Date"].min(), pd.Timestamp(det["as_of"]), freq="D"), fill_value=0).std() or 0.0)
        guidance = demand_based_guidance(d["forecast_total_units"], det["dead_stock_risk_score"], det["classification"])
        try:
            calc = reorder_calc(daily, dsd, req.get("on_hand_qty"), req.get("lead_time_days"),
                                req.get("lead_time_sd_days", 0.0), req.get("service_level", 0.95),
                                req.get("on_order_qty", 0.0), req.get("moq"),
                                req.get("review_period_days", 7.0), det["dead_stock_risk_score"])
        except ValueError as e:
            raise InvalidRequestError(str(e)) from e
        out = {**d, "reorder": calc, "guidance": guidance, "dead_stock_classification": det["classification"],
               "requires_human_approval": True,
               "approval_note": "No purchase order is executed; inventory and supplier inputs must be verified."}
        out["recommended_action"] = guidance["purchase_guidance"]
        return out

    def anomaly_detection(self, req: dict) -> dict:
        feat, sales, out = self._base(req)
        if feat is None: return out
        s = sales.assign(IsExactDuplicate=sales.duplicated(["InvoiceNo", "Quantity", "UnitPrice", "Date"]))
        tq = transaction_quality(s)
        cols = [c for c in ("InvoiceNo", "Quantity", "UnitPrice", "flags", "what_was_unusual", "why_review")
                if c in tq.columns]
        out.update(status="OK", model_version="rules-anomaly-1.0", model_trained_at_utc=None,
                   pipeline_version=self.ds_meta.get("pipeline_version"),
                   transaction_quality_flags=tq[cols].to_dict("records"),
                   prediction={"n_flagged": int(len(tq))},
                   explanation="Rule-based transaction-quality checks; each alert states what was unusual and why it "
                               "merits review. Records are reported, never removed, and are not fraud findings.")
        return out

    def reduction_actions(self, req: dict) -> dict:
        feat, sales, out = self._base(req)
        if feat is None: return out
        c = self._classified(feat, sales, req)
        mv = self.movement_classification(req)
        row = {**c.to_dict(), "abc_class": mv["abc_class"], "xyz_class": mv["xyz_class"], "abc_xyz": mv["abc_xyz"],
               "trend_class": mv["trend_class"], "speed_class": mv["speed_class"],
               "high_value_declining": mv["abc_class"] == "A" and mv["trend_class"] == "Declining", "revenue_to_date": float(sales["LineValue"].sum())}
        q = build_queue(pd.DataFrame([c.to_dict()]), pd.DataFrame([{**row, "StockCode": c["StockCode"]}]))
        missing = ["on_hand_qty", "unit_cost", "margin", "supplier terms", "lifecycle status"]
        if q.empty:
            out.update(status="OK", prediction={"intervention": None}, recommended_action="No intervention required.",
                       explanation="Product is not flagged as at-risk by demand evidence.", model_version=self.ds_meta["model_version"])
            return out
        r = q.iloc[0].to_dict()
        out.update(status="OK", **self._metadata(self.ds_meta), prediction={"priority": r["priority"]},
                   recommended_action=r["recommended_actions"], intervention=r.get("intervention"),
                   risk_classification=r["classification"],
                   expected_impact_direction=r.get("expected_impact_direction"),
                   inventory_value_impact=r.get("inventory_value_impact"),
                   requires_human_approval=bool(r.get("requires_human_approval", True)),
                   required_information=r.get("required_information"),
                   explanation=five_part_explanation({**r, "status_type": c["status_type"], "risk_explanation": r["supporting_evidence"]}, missing),
                   confidence={"evidence_quality": r["confidence"]})
        return out

    def health(self) -> dict:
        """Backend readiness probe: artifact versions and availability, no prediction."""
        return {"status": "OK", "schema_version": SCHEMA_VERSION,
                "dead_stock": self._metadata(self.ds_meta),
                "forecasting": self._metadata(self.fc_meta),
                "movement": self._metadata(self.mv_meta),
                "anomaly_model_version": "rules-anomaly-1.0",
                "deployed_dead_stock_predictor": self.ds_meta.get("deployed_predictor")}

    def management_summary(self) -> dict:
        p = REPORT_DIR / "management_summary.json"
        if not p.exists(): raise ModelUnavailableError("management summary not generated: run scripts/ml_run_intelligence.py")
        return json.loads(p.read_text())
