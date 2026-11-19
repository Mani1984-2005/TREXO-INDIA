"""Module E: reorder intelligence. Never invents a purchase quantity: when required
inputs are missing the result is a demand-based guidance with the missing fields listed."""
from __future__ import annotations
import math
from statistics import NormalDist

REQUIRED_FOR_QUANTITY = ["on_hand_qty", "lead_time_days"]
OPTIONAL = ["lead_time_sd_days", "on_order_qty", "moq", "service_level", "review_period_days"]


def reorder_calc(daily_demand_mean: float, daily_demand_sd: float, on_hand_qty=None, lead_time_days=None,
                 lead_time_sd_days=0.0, service_level=0.95, on_order_qty=0.0, moq=None,
                 review_period_days=7.0, dead_stock_risk_score: float | None = None,
                 risk_block_threshold: float = 0.6) -> dict:
    """Classic (s, S)-style calculation:
      z = Phi^-1(service_level); sigma_LT = sqrt(L*sd_d^2 + d^2*sd_L^2)
      safety = z*sigma_LT ; ROP = d*L + safety ; order-up-to = d*(L+R) + safety
      order = max(0, order-up-to - on_hand - on_order), rounded up to MOQ.
    Blocked (order 0) when dead-stock risk >= risk_block_threshold."""
    missing = [k for k, v in (("on_hand_qty", on_hand_qty), ("lead_time_days", lead_time_days)) if v is None]
    base = {"daily_demand_mean": daily_demand_mean, "inputs_missing": missing}
    if daily_demand_mean < 0 or daily_demand_sd < 0:
        raise ValueError("demand statistics must be non-negative")
    if missing:
        base.update(status="INSUFFICIENT_INPUTS", recommended_order_qty=None,
                    guidance="Demand-based guidance only; no purchase quantity can be recommended "
                             f"without: {', '.join(missing)}.")
        return base
    if on_hand_qty < 0 or lead_time_days < 0 or not 0.5 <= service_level < 1:
        raise ValueError("invalid inventory inputs")
    z = NormalDist().inv_cdf(service_level)
    sigma_lt = math.sqrt(lead_time_days * daily_demand_sd ** 2 + (daily_demand_mean ** 2) * lead_time_sd_days ** 2)
    safety = z * sigma_lt
    rop = daily_demand_mean * lead_time_days + safety
    up_to = daily_demand_mean * (lead_time_days + review_period_days) + safety
    position = on_hand_qty + (on_order_qty or 0.0)
    order = max(0.0, up_to - position)
    if moq and order > 0:
        order = math.ceil(order / moq) * moq
    cover_days = on_hand_qty / daily_demand_mean if daily_demand_mean > 0 else math.inf
    blocked = dead_stock_risk_score is not None and dead_stock_risk_score >= risk_block_threshold
    base.update(status="BLOCKED_BY_DEAD_STOCK_RISK" if blocked else "CALCULATED", safety_stock=safety,
                reorder_point=rop, order_up_to_level=up_to, inventory_position=position,
                demand_cover_days=cover_days, below_reorder_point=position <= rop,
                stockout_risk="HIGH" if position <= daily_demand_mean * lead_time_days else
                              ("MEDIUM" if position <= rop else "LOW"),
                excess_inventory_risk="HIGH" if cover_days > 180 else ("MEDIUM" if cover_days > 90 else "LOW"),
                recommended_order_qty=0.0 if blocked else order)
    if blocked:
        base["guidance"] = "Order suppressed: calibrated dead-stock risk is at/above the block threshold."
    return base


def demand_based_guidance(forecast_4w: float, risk_score: float, classification: str) -> dict:
    """Used when stock/lead-time inputs are absent. No quantity to buy is produced."""
    if classification in ("Critical Dead-Stock Risk", "Confirmed Dead Stock"):
        g = "DO_NOT_REORDER"
    elif classification == "At-Risk Stock":
        g = "PAUSE_REORDER_PENDING_REVIEW"
    elif classification == "Slow Moving Stock":
        g = "REDUCE_FUTURE_PURCHASES"
    else:
        g = "DEMAND_SUPPORTS_REPLENISHMENT"
    return {"purchase_guidance": g, "expected_demand_next_4_weeks_units": float(forecast_4w),
            "recommended_order_qty": None,
            "missing_for_quantity": REQUIRED_FOR_QUANTITY,
            "note": "Expected demand is a forecast, not an order quantity."}
