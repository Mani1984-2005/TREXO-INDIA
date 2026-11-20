"""Lazy, thread-safe access to the TREXO ML services.

Model bundles are loaded once per process.  A failure to load is reported as
``MODEL_UNAVAILABLE`` (HTTP 503) rather than crashing the API or fabricating a
prediction.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ..config import REPO_ROOT
from ..security import ApiError

_lock = threading.RLock()
_inference = None
_retail = None
_load_errors: dict[str, str] = {}


def _import_ml():
    """Import the ML package, translating import errors into a clean API error."""
    try:
        from trexo.ml.inference.service import InferenceService  # noqa: F401
        from trexo.ml.retail.service import RetailIntelligenceService  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment failure
        raise ApiError(
            "ML_PACKAGE_UNAVAILABLE",
            "The TREXO ML package could not be imported; install requirements-lock.txt",
            503,
            {"error": str(exc)},
        ) from exc


def inference():
    global _inference
    with _lock:
        if _inference is None:
            _import_ml()
            from trexo.ml.inference.service import InferenceService

            try:
                _inference = InferenceService()
            except Exception as exc:
                _load_errors["inference"] = str(exc)
                raise ApiError(
                    "MODEL_UNAVAILABLE",
                    "ML model artifacts are unavailable; run the training scripts first",
                    503,
                    {"error": str(exc)},
                ) from exc
        return _inference


def retail():
    global _retail
    with _lock:
        if _retail is None:
            _import_ml()
            from trexo.ml.retail.service import RetailIntelligenceService

            try:
                _retail = RetailIntelligenceService()
            except Exception as exc:
                _load_errors["retail"] = str(exc)
                raise ApiError(
                    "MODEL_UNAVAILABLE",
                    "Retail intelligence model artifacts are unavailable",
                    503,
                    {"error": str(exc)},
                ) from exc
        return _retail


def reset() -> None:
    """Test helper: drop cached services so artifacts can be re-read."""
    global _inference, _retail
    with _lock:
        _inference = None
        _retail = None
        _load_errors.clear()


def _raise_from_ml(exc: Exception) -> None:
    """Translate ML exceptions into API errors without leaking tracebacks."""
    name = type(exc).__name__
    if name == "InvalidRequestError":
        raise ApiError("INVALID_REQUEST", str(exc), 422)
    if name == "ModelUnavailableError":
        raise ApiError("MODEL_UNAVAILABLE", str(exc), 503)
    raise ApiError("ML_ERROR", "The ML layer failed to process this request", 500, {"error": str(exc)})


def _safe(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - translated below
        _raise_from_ml(exc)


# ---------------------------------------------------------------- ML facade
def dead_stock(payload: dict) -> dict:
    return _safe(inference().dead_stock_detection, payload)


def forecast(payload: dict, horizon_weeks: int) -> dict:
    return _safe(inference().demand_forecast, payload, horizon_weeks)


def movement(payload: dict) -> dict:
    return _safe(inference().movement_classification, payload)


def anomalies(payload: dict) -> dict:
    return _safe(inference().anomaly_detection, payload)


def reorder(payload: dict) -> dict:
    return _safe(inference().reorder_recommendation, payload)


def reduction_actions(payload: dict) -> dict:
    return _safe(inference().reduction_actions, payload)


def summary() -> dict:
    return _safe(inference().management_summary)


def health() -> dict:
    return _safe(inference().health)


def inventory_balances(payload: dict) -> dict:
    return _safe(retail().inventory_balances, payload)


def stock_priority(payload: dict) -> dict:
    return _safe(retail().stock_priority, payload)


def pricing_scenarios(payload: dict) -> dict:
    return _safe(retail().pricing_scenarios, payload)


def bundle_recommendations(payload: dict) -> dict:
    return _safe(retail().bundle_recommendations, payload)


def recovery_plan(payload: dict) -> dict:
    return _safe(retail().recovery_recommendations, payload)


# ------------------------------------------------------------- model registry
def _models_root() -> Path:
    return REPO_ROOT / "models"


def list_models() -> list[dict]:
    root = _models_root()
    out = []
    if not root.exists():
        return out
    for kind_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        latest_file = kind_dir / "LATEST"
        versions = sorted(
            p.name for p in kind_dir.iterdir() if p.is_dir() and (p / "metadata.json").exists()
        )
        if not versions:
            continue
        latest = latest_file.read_text(encoding="utf-8").strip() if latest_file.exists() else None
        metadata: dict = {}
        if latest and (kind_dir / latest / "metadata.json").exists():
            try:
                metadata = json.loads((kind_dir / latest / "metadata.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {"error": "metadata unreadable"}
        out.append({"kind": kind_dir.name, "latest": latest, "versions": versions, "metadata": metadata})
    return out


def model(kind: str) -> dict:
    for entry in list_models():
        if entry["kind"] == kind:
            return entry
    raise ApiError("MODEL_KIND_NOT_FOUND", f"No model kind '{kind}' is registered", 404)


def _is_safe_version_name(version: str) -> bool:
    return bool(version) and "/" not in version and "\\" not in version and ".." not in version


def activate(kind: str, version: str) -> dict:
    """Point ``LATEST`` at a previously trained, checksum-verified version."""
    if not _is_safe_version_name(version):
        raise ApiError("INVALID_VERSION", "Version name is not allowed", 422)
    root = _models_root()
    target = root / kind / version
    if not (target / "metadata.json").exists():
        raise ApiError("VERSION_NOT_FOUND", f"{kind}/{version} does not exist", 404)
    try:
        from trexo.ml.registry.registry import load_model_bundle

        load_model_bundle(kind, version)
    except Exception as exc:  # noqa: BLE001
        raise ApiError("VERSION_INVALID", "Artifact checksum verification failed", 409, {"error": str(exc)}) from exc
    (root / kind / "LATEST").write_text(version, encoding="utf-8")
    return model(kind)


def _load_errors_view() -> dict[str, str]:
    return dict(_load_errors)
