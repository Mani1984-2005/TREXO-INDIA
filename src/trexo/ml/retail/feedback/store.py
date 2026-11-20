"""Feedback ledger (SQLite) + controlled-experiment helpers + retraining gate.
Nothing here changes a production model or executes a price/purchase action."""
from __future__ import annotations
import hashlib, json, sqlite3, datetime as dt
import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations(rec_id TEXT PRIMARY KEY, created_at TEXT, product_id TEXT, model_version TEXT,
  risk_classification TEXT, risk_score REAL, recommended_action TEXT, suggested_discount REAL, suggested_price REAL,
  predicted_units REAL, predicted_gross_profit REAL, payload TEXT);
CREATE TABLE IF NOT EXISTS approvals(rec_id TEXT PRIMARY KEY, decided_at TEXT, approver TEXT, decision TEXT, approved_discount REAL, approved_price REAL, note TEXT);
CREATE TABLE IF NOT EXISTS executions(rec_id TEXT PRIMARY KEY, start_date TEXT, end_date TEXT, executed_discount REAL, executed_price REAL, arm TEXT, experiment_id TEXT);
CREATE TABLE IF NOT EXISTS outcomes(rec_id TEXT PRIMARY KEY, recorded_at TEXT, units_sold REAL, avg_selling_price REAL, gross_profit REAL,
  remaining_inventory REAL, customer_response TEXT, verified INTEGER);
"""


class FeedbackStore:
    def __init__(self, path=":memory:"):
        self.con = sqlite3.connect(path); self.con.executescript(SCHEMA)

    def log_recommendation(self, rec: dict) -> str:
        rid = rec.get("rec_id") or hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:16]
        self.con.execute("INSERT INTO recommendations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            rid, dt.datetime.now(dt.timezone.utc).isoformat(), rec["product_id"], rec.get("model_version"), rec.get("risk_classification"),
            rec.get("risk_score"), rec.get("recommended_action"), rec.get("suggested_discount"), rec.get("suggested_price"),
            rec.get("predicted_units"), rec.get("predicted_gross_profit"), json.dumps(rec, default=str)))
        self.con.commit(); return rid

    def record_approval(self, rec_id, approver, decision, approved_discount=None, approved_price=None, note=""):
        if decision not in ("APPROVED", "REJECTED", "MODIFIED"): raise ValueError("decision must be APPROVED/REJECTED/MODIFIED")
        if not approver: raise ValueError("approver is required: actions need an accountable business user")
        self._need("recommendations", rec_id)
        self.con.execute("INSERT OR REPLACE INTO approvals VALUES (?,?,?,?,?,?,?)", (rec_id, dt.datetime.now(dt.timezone.utc).isoformat(), approver, decision, approved_discount, approved_price, note)); self.con.commit()

    def record_execution(self, rec_id, start_date, end_date, executed_discount, executed_price, arm="treatment", experiment_id=None):
        a = self.con.execute("SELECT decision FROM approvals WHERE rec_id=?", (rec_id,)).fetchone()
        if not a or a[0] == "REJECTED": raise PermissionError("cannot record execution of an offer that was not approved")
        self.con.execute("INSERT OR REPLACE INTO executions VALUES (?,?,?,?,?,?,?)", (rec_id, str(start_date), str(end_date), executed_discount, executed_price, arm, experiment_id)); self.con.commit()

    def record_outcome(self, rec_id, units_sold, avg_selling_price, gross_profit, remaining_inventory, customer_response="", verified=True):
        if units_sold < 0 or remaining_inventory < 0: raise ValueError("negative outcome values")
        self._need("executions", rec_id)
        self.con.execute("INSERT OR REPLACE INTO outcomes VALUES (?,?,?,?,?,?,?,?)", (rec_id, dt.datetime.now(dt.timezone.utc).isoformat(), units_sold, avg_selling_price, gross_profit, remaining_inventory, customer_response, int(verified))); self.con.commit()

    def _need(self, table, rec_id):
        if not self.con.execute(f"SELECT 1 FROM {table} WHERE rec_id=?", (rec_id,)).fetchone(): raise KeyError(f"{rec_id} not found in {table}")

    def joined(self) -> pd.DataFrame:
        return pd.read_sql_query("""SELECT r.*, a.decision, a.approver, e.executed_discount, e.executed_price, e.arm, e.experiment_id,
            o.units_sold, o.avg_selling_price, o.gross_profit, o.remaining_inventory, o.verified
            FROM recommendations r LEFT JOIN approvals a USING(rec_id) LEFT JOIN executions e USING(rec_id) LEFT JOIN outcomes o USING(rec_id)""", self.con)

    def prediction_vs_actual(self) -> dict:
        d = self.joined(); d = d[(d["verified"] == 1) & d["units_sold"].notna() & d["predicted_units"].notna()]
        if d.empty: return {"n": 0, "note": "no verified outcomes yet"}
        err = d["units_sold"] - d["predicted_units"]
        out = {"n": int(len(d)), "units_MAE": float(err.abs().mean()), "units_bias": float(err.sum() / max(d["predicted_units"].sum(), 1e-9))}
        g = d.dropna(subset=["gross_profit", "predicted_gross_profit"])
        if len(g): out["gross_profit_MAE"] = float((g["gross_profit"] - g["predicted_gross_profit"]).abs().mean())
        return out


def assign_arm(unit_id: str, experiment_id: str, p_treat: float = 0.5, salt: str = "trexo") -> str:
    """Deterministic randomisation by hash: same unit -> same arm; reproducible and auditable."""
    h = int(hashlib.sha256(f"{salt}|{experiment_id}|{unit_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "treatment" if h < p_treat else "control"


def analyse_experiment(df: pd.DataFrame, outcome: str = "units_sold", min_per_arm: int = 20, n_boot: int = 2000, seed: int = 42) -> dict:
    """Difference in means treatment - control with bootstrap CI. Refuses to conclude with too few units."""
    t = df[df["arm"] == "treatment"][outcome].dropna().to_numpy(float); c = df[df["arm"] == "control"][outcome].dropna().to_numpy(float)
    if len(t) < min_per_arm or len(c) < min_per_arm:
        return {"status": "INSUFFICIENT_DATA", "n_treatment": len(t), "n_control": len(c), "min_per_arm": min_per_arm}
    rng = np.random.default_rng(seed)
    diffs = [rng.choice(t, len(t)).mean() - rng.choice(c, len(c)).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"status": "OK", "effect": float(t.mean() - c.mean()), "ci95": [float(lo), float(hi)], "n_treatment": len(t), "n_control": len(c),
            "significant_at_95": bool(lo > 0 or hi < 0)}


def retraining_gate(n_verified_outcomes: int, candidate_metric: float, incumbent_metric: float, higher_is_better: bool,
                    min_outcomes: int = 200, min_improvement: float = 0.02, human_approval: bool = False) -> dict:
    reasons = []
    if n_verified_outcomes < min_outcomes: reasons.append(f"need >= {min_outcomes} verified outcomes (have {n_verified_outcomes})")
    gain = (candidate_metric - incumbent_metric) if higher_is_better else (incumbent_metric - candidate_metric)
    if gain < min_improvement: reasons.append(f"improvement {gain:.4f} below required {min_improvement}")
    if not human_approval: reasons.append("human approval missing")
    return {"promote": not reasons, "reasons": reasons, "note": "A promote=True result still requires a human to run the deployment; nothing is swapped automatically."}
