"""Chronological, purged cutoff splits for the dead-stock risk task."""
from __future__ import annotations
import pandas as pd
from ..config import HorizonConfig


def make_cutoffs(data_start, cfg: HorizonConfig = HorizonConfig()) -> dict:
    start = pd.Timestamp(data_start) + pd.Timedelta(days=cfg.min_history_days)
    # first cutoff: data_start + min_history, then fixed step; sample by 30d
    first = pd.Timestamp("2011-03-10")  # = 2010-12-01 + 99d; >= min_history, month-aligned
    assert first >= start
    last_train = pd.Timestamp(cfg.last_train_cutoff)
    train = list(pd.date_range(first, last_train, freq=f"{cfg.cutoff_step_days}D"))
    val, test = pd.Timestamp(cfg.val_cutoff), pd.Timestamp(cfg.test_cutoff)
    H = pd.Timedelta(days=cfg.label_horizon_days)
    # purge checks: every label window must close before the next split's cutoff
    assert train[-1] + H <= val, "train label window overlaps validation cutoff"
    assert val + H <= test, "validation label window overlaps test cutoff"
    return {"train": train, "val": val, "test": test}


def forward_chain_folds(train_cutoffs, horizon_days: int):
    """Expanding-window folds inside the training period, purged so the training
    label windows close at or before the validation cutoff."""
    H = pd.Timedelta(days=horizon_days)
    folds = []
    for i, v in enumerate(train_cutoffs):
        tr = [c for c in train_cutoffs[:i] if c + H <= v]
        if tr:
            folds.append((tr, v))
    return folds
