"""Module B: dead-stock RISK prediction (future 60-day sales inactivity).

TARGET LIMITATION: the dataset has no stock balances, so y=1 means *no valid sale
in the next H days*, i.e. demand inactivity. It is NOT a claim of physical dead stock.
"""
from __future__ import annotations
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from ..config import SEED
from ..features.product_features import FEATURE_COLUMNS

# features carrying no sign of the cutoff calendar position (one year only -> calendar
# features cannot generalise and would leak position-in-year); history_days is excluded
# for the same reason (it is a pure function of the cutoff date).
MODEL_FEATURES = [c for c in FEATURE_COLUMNS if c != "history_days"]


class Log1pSkew(BaseEstimator, TransformerMixin):
    """log1p on non-negative skewed columns (all features here are >=0)."""
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        return np.log1p(np.clip(np.asarray(X, float), 0, None))


def candidates() -> dict:
    return {
        "logistic_regression": (Pipeline([("log", Log1pSkew()), ("sc", StandardScaler()),
                                          ("m", LogisticRegression(max_iter=2000, random_state=SEED))]),
                                [{"m__C": c} for c in (0.03, 0.3, 3.0)]),
        "random_forest": (RandomForestClassifier(n_estimators=300, min_samples_leaf=10, n_jobs=-1,
                                                 random_state=SEED),
                          [{"min_samples_leaf": l, "max_depth": d} for l in (5, 20) for d in (6, None)]),
        "hist_gradient_boosting": (HistGradientBoostingClassifier(random_state=SEED, early_stopping=False),
                                   [{"learning_rate": lr, "max_iter": it, "max_depth": d, "min_samples_leaf": 40}
                                    for lr in (0.03, 0.1) for it in (100, 250) for d in (3, 5)]),
    }


def lightgbm_candidate():
    try:
        import lightgbm as lgb
    except ImportError:
        return None
    return (lgb.LGBMClassifier(random_state=SEED, verbose=-1, n_jobs=2, subsample_freq=1),
            [{"n_estimators": n, "learning_rate": lr, "num_leaves": nl, "min_child_samples": 40,
              "subsample": 0.8, "colsample_bytree": 0.8}
             for n in (150, 400) for lr in (0.03, 0.08) for nl in (7, 15)])


def with_params(est, params):
    e = clone(est)
    e.set_params(**params)
    return e
