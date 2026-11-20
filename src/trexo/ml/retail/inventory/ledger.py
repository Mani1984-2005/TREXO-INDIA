"""Auditable inventory movement ledger. Stock is ALWAYS derived from verified events
(never inferred from sales). Events are validated, never silently altered; rejected
events are returned with reasons."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

SIGN = {"OPENING": 1, "RECEIPT": 1, "RETURN": 1, "TRANSFER_IN": 1, "SALE": -1, "DAMAGE": -1,
        "TRANSFER_OUT": -1, "ADJUSTMENT": 0}          # ADJUSTMENT uses `direction` (+1/-1)
RESERVATION = {"RESERVE": 1, "RELEASE": -1}
TYPES = set(SIGN) | set(RESERVATION)
# same-day processing order: stock-in before stock-out so a same-day receipt can serve a sale
ORDER = {"OPENING": 0, "RECEIPT": 1, "TRANSFER_IN": 1, "RETURN": 2, "ADJUSTMENT": 3, "RESERVE": 4,
         "RELEASE": 4, "SALE": 5, "DAMAGE": 6, "TRANSFER_OUT": 6}
EVENT_COLUMNS = ["event_id", "product_id", "location", "ts", "type", "qty", "unit_cost", "direction", "expiry_date", "unit_price"]


@dataclass
class LedgerResult:
    accepted: pd.DataFrame
    rejected: pd.DataFrame
    balances: pd.DataFrame      # product x location
    layers: pd.DataFrame        # FIFO layers still on hand
    consumption: pd.DataFrame   # which layers each outflow consumed (audit trail)


def validate_events(ev: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = ev.copy()
    for c in EVENT_COLUMNS:
        if c not in d.columns: d[c] = np.nan
    d["ts"] = pd.to_datetime(d["ts"], errors="coerce")
    d["qty"] = pd.to_numeric(d["qty"], errors="coerce")
    reason = pd.Series("", index=d.index, dtype=object)
    def mark(mask, text):
        nonlocal reason
        reason = reason.mask((reason == "") & mask, text)
    mark(d["event_id"].isna() | d["product_id"].isna(), "MISSING_ID")
    mark(~d["type"].isin(TYPES), "UNKNOWN_EVENT_TYPE")
    mark(d["ts"].isna(), "MISSING_OR_INVALID_DATE")
    mark(d["qty"].isna() | (d["qty"] <= 0), "NON_POSITIVE_OR_MISSING_QTY")
    mark((d["type"] == "ADJUSTMENT") & ~d["direction"].isin([1, -1]), "ADJUSTMENT_NEEDS_DIRECTION")
    mark(d["type"].isin(["OPENING", "RECEIPT"]) & (pd.to_numeric(d["unit_cost"], errors="coerce") < 0), "NEGATIVE_COST")
    mark(d["event_id"].duplicated(keep="first") & d["event_id"].notna(), "DUPLICATE_EVENT_ID")
    d["reject_reason"] = reason
    return d[reason == ""].drop(columns="reject_reason"), d[reason != ""]


def _signed(d: pd.DataFrame) -> pd.Series:
    s = d["type"].map(SIGN).astype(float)
    adj = d["type"] == "ADJUSTMENT"
    s[adj] = d.loc[adj, "direction"].astype(float)
    return s * d["qty"]


def process_ledger(events: pd.DataFrame, allow_negative: bool = False) -> LedgerResult:
    """Replay events chronologically with FIFO layers per (product, location).
    An outflow exceeding available layers is REJECTED (reason NEGATIVE_BALANCE) unless allow_negative."""
    ok, bad = validate_events(events)
    ok = ok.assign(_o=ok["type"].map(ORDER)).sort_values(["ts", "_o", "event_id"], kind="mergesort")
    layers: dict[tuple, list[list]] = {}
    reserved: dict[tuple, float] = {}
    rejected_rt, consumption, accepted_idx = [], [], []
    for r in ok.itertuples(index=False):
        key = (r.product_id, r.location); L = layers.setdefault(key, [])
        t = r.type
        if t in RESERVATION:
            cur = reserved.get(key, 0.0); new = cur + RESERVATION[t] * r.qty
            on = sum(x[1] for x in L)
            if new < 0 or new > on + 1e-9:
                rejected_rt.append((r.event_id, "RESERVATION_EXCEEDS_STOCK" if new > 0 else "RELEASE_EXCEEDS_RESERVED")); continue
            reserved[key] = new; accepted_idx.append(r.event_id); continue
        sign = SIGN[t] if t != "ADJUSTMENT" else int(r.direction)
        if sign > 0:
            cost = r.unit_cost if pd.notna(r.unit_cost) else np.nan
            # returns re-enter as a NEW layer dated at the return (conservative: age restarts)
            L.append([r.ts, float(r.qty), cost, r.expiry_date, r.event_id]); accepted_idx.append(r.event_id)
        else:
            need = float(r.qty); have = sum(x[1] for x in L)
            if need > have + 1e-9 and not allow_negative:
                rejected_rt.append((r.event_id, f"NEGATIVE_BALANCE (needs {need:g}, on hand {have:g})")); continue
            while need > 1e-12 and L:
                lay = L[0]; take = min(lay[1], need); lay[1] -= take; need -= take
                consumption.append((r.event_id, r.product_id, r.location, lay[4], take, lay[2], r.ts))
                if lay[1] <= 1e-12: L.pop(0)
            accepted_idx.append(r.event_id)
            # reservations may not exceed on-hand after outflow
            reserved[key] = min(reserved.get(key, 0.0), sum(x[1] for x in L))
    acc = ok[ok["event_id"].isin(accepted_idx)].drop(columns="_o")
    rej_rt = pd.DataFrame(rejected_rt, columns=["event_id", "reject_reason"])
    rej_rt = ok.drop(columns="_o").merge(rej_rt, on="event_id")
    rejected = pd.concat([bad, rej_rt], ignore_index=True)
    lay_rows = [(k[0], k[1], x[4], x[0], x[1], x[2], x[3]) for k, L in layers.items() for x in L if x[1] > 1e-12]
    lay = pd.DataFrame(lay_rows, columns=["product_id", "location", "layer_event_id", "received_ts", "qty_remaining", "unit_cost", "expiry_date"])
    keys = set(layers) | set(reserved)
    bal = pd.DataFrame([(k[0], k[1], sum(x[1] for x in layers.get(k, [])), reserved.get(k, 0.0)) for k in keys],
                       columns=["product_id", "location", "on_hand", "reserved"])
    bal["available"] = bal["on_hand"] - bal["reserved"]
    cons = pd.DataFrame(consumption, columns=["event_id", "product_id", "location", "layer_event_id", "qty", "unit_cost", "ts"])
    return LedgerResult(acc, rejected, bal.sort_values(["product_id", "location"]).reset_index(drop=True), lay, cons)


def reconcile(balances: pd.DataFrame, reported: pd.DataFrame, tol: float = 1e-9) -> pd.DataFrame:
    """Compare ledger on_hand with a reported physical count. Differences are REPORTED, never auto-corrected."""
    m = balances.merge(reported, on=["product_id", "location"], how="outer", suffixes=("_ledger", "_reported"))
    m["on_hand"] = m["on_hand"].fillna(0.0); m["reported_on_hand"] = m["reported_on_hand"].fillna(np.nan)
    m["difference"] = m["reported_on_hand"] - m["on_hand"]
    m["status"] = np.where(m["reported_on_hand"].isna(), "NOT_COUNTED",
                           np.where(m["difference"].abs() <= tol, "MATCH", "DISCREPANCY"))
    return m


def incoming_po_by_product(po: pd.DataFrame, as_of) -> pd.Series:
    """Open PO quantity not yet received. Columns: po_id, product_id, qty, expected_date, status."""
    p = po.copy(); p = p[(p["status"].fillna("OPEN") == "OPEN") & (pd.to_numeric(p["qty"], errors="coerce") > 0)]
    return p.groupby("product_id")["qty"].sum()
