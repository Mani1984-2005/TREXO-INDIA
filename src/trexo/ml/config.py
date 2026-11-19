"""Central, versioned configuration for the TREXO ML layer.

Every number here is either (a) a structural constant taken from the audited
dataset/policy documents, or (b) a *default* that is overwritten by values
calibrated from training-period data (see dead_stock.calibration). Nothing here
is an approved business rule; governance approval status is unchanged.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_FILE = REPO_ROOT / "data" / "raw" / "Online Retail.xlsx"
ML_DATA_DIR = REPO_ROOT / "data" / "ml"
REPORT_DIR = REPO_ROOT / "reports" / "ml"
MODEL_DIR = REPO_ROOT / "models"
SEED = 42
PIPELINE_VERSION = "ml-1.1.0"
SCHEMA_VERSION = "1.0"

# Governance decision D01 (approved): the bad-debt invoice group is one financial
# event and must never be treated as product demand. Exclusion is by invoice, in
# first-match priority, before every other rule. The source rows are preserved.
D01_EXCLUSION_REASON = "D01_BAD_DEBT_GROUP"
D01_BAD_DEBT_INVOICES = ("A563185", "A563186", "A563187")
D01_EVENT_GROUP = "BAD_DEBT_A563185_A563187"
D01_DECISION = "D01_APPROVED"
D01_REASON = ("Approved D01 governance decision: complete bad-debt invoice group is a "
              "financial adjustment event, excluded from product demand/movement/"
              "forecasting/dead-stock features, labels, evaluation and recommendations.")

# Non-merchandise StockCodes, from docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md
# rules 2-11 (proposal, not approved). Used ONLY to keep these rows out of
# product-demand features; the rows themselves are never deleted from source.
# StockCode B is retained here only as a defensive fallback: in this dataset all
# three B rows are the D01 group, and D01 is matched first. Any future non-D01 B
# row must not be silently treated as an ordinary sale.
NON_PRODUCT_CODES = {
    "POST", "DOT", "C2", "BANK CHARGES", "AMAZONFEE", "CRUK",
    "B", "D", "M", "m", "S", "PADS",
}
NON_PRODUCT_PREFIXES = ("GIFT_", "DCGS")


@dataclass
class HorizonConfig:
    label_horizon_days: int = 60          # future window for inactivity label
    cutoff_step_days: int = 30            # spacing of training cutoffs
    min_history_days: int = 60            # first cutoff is at least this far from data start
    # chronological split (cutoff dates). Windows are purged so that a train
    # label window never overlaps a later cutoff's feature window end.
    test_cutoff: str = "2011-10-10"       # window (10-10, 12-09] is last full 60d
    val_cutoff: str = "2011-08-10"        # window ends 10-09 <= test cutoff
    last_train_cutoff: str = "2011-06-10" # window ends 08-09 <= val cutoff


@dataclass
class ClassificationThresholds:
    """Defaults are overwritten by calibrated values (data/ml/calibration.json)."""
    healthy_max_score: float = 0.20
    normal_max_score: float = 0.40
    slow_max_score: float = 0.60
    at_risk_max_score: float = 0.80
    min_invoices_for_evidence: int = 3
    min_age_days_for_evidence: int = 60
    seasonal_concentration_share: float = 0.70   # share of qty in best 2 months
    fast_velocity_pctl: float = 0.75
    xyz_x_max_cv: float = 0.5
    xyz_y_max_cv: float = 1.0
    abc_a_share: float = 0.70
    abc_b_share: float = 0.90
    trend_decline_ratio: float = 0.5
    trend_growth_ratio: float = 1.5


def load_calibrated_thresholds() -> ClassificationThresholds:
    p = ML_DATA_DIR / "calibration.json"
    t = ClassificationThresholds()
    if p.exists():
        for k, v in json.loads(p.read_text()).get("classification_thresholds", {}).items():
            if hasattr(t, k):
                setattr(t, k, v)
    return t
