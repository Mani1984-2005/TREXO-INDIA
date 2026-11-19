#!/usr/bin/env bash
# Full reproducible ML run (from repo root). Requires: pip install -r requirements-lock.txt lightgbm pytest
set -euo pipefail
export PYTHONPATH=src
python scripts/ml_prepare_data.py
python scripts/ml_train_dead_stock.py
python scripts/ml_train_forecasting.py
python scripts/ml_run_intelligence.py
python scripts/ml_run_simulation.py
python -m pytest tests -q
