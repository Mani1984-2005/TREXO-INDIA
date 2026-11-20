"""TREXO-INDIA unified backend API.

The ML implementation lives in ``src/trexo/ml`` (the audited, versioned
repository package).  This backend is a thin, validated HTTP layer on top of
it plus the store-operations domain used by the React frontend.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:  # pragma: no cover - import bootstrapping
    sys.path.insert(0, str(_SRC))

__version__ = "1.0.0"
