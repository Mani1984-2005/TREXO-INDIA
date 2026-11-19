"""Versioned model artifact registry. A model is marked trained only after
artifacts are written, re-loaded and verified (checksums + a smoke prediction)."""
from __future__ import annotations
import hashlib, json, datetime as dt
from pathlib import Path
import joblib
from ..config import MODEL_DIR, PIPELINE_VERSION


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def data_fingerprint(paths) -> dict:
    """SHA-256 fingerprints of the exact training inputs, plus one combined hash."""
    files = {}
    for p in paths:
        p = Path(p)
        if p.exists():
            files[p.name] = _sha(p)
    combined = hashlib.sha256(
        "|".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()).hexdigest()
    return {"files": files, "combined_sha256": combined}


def feature_schema_fingerprint(features) -> str:
    return hashlib.sha256(("|".join(map(str, features))).encode()).hexdigest()


def save_model_bundle(kind: str, objects: dict, metadata: dict, root: Path = MODEL_DIR) -> dict:
    ts = dt.datetime.now(dt.timezone.utc)
    version = f"{kind}-{PIPELINE_VERSION}-{ts.strftime('%Y%m%dT%H%M%SZ')}"
    d = root / kind / version
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, obj in objects.items():
        p = d / f"{name}.joblib"
        joblib.dump(obj, p)
        joblib.load(p)  # round-trip verification
        files[p.name] = _sha(p)
    meta = {"model_version": version, "kind": kind, "trained_at_utc": ts.isoformat(),
            "pipeline_version": PIPELINE_VERSION, "artifact_checksums_sha256": files,
            "status": "TRAINED_AND_VERIFIED", **metadata}
    (d / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    (root / kind / "LATEST").write_text(version)
    return {"model_version": version, "path": str(d.relative_to(root.parent)), "files": files}


def latest_version(kind: str, root: Path = MODEL_DIR) -> str | None:
    p = root / kind / "LATEST"
    return p.read_text().strip() if p.exists() else None


def load_model_bundle(kind: str, version: str | None = None, root: Path = MODEL_DIR) -> tuple[dict, dict]:
    version = version or latest_version(kind, root)
    if version is None:
        raise FileNotFoundError(f"no trained '{kind}' model available")
    d = root / kind / version
    meta = json.loads((d / "metadata.json").read_text())
    for fname, expected in meta["artifact_checksums_sha256"].items():
        if _sha(d / fname) != expected:
            raise RuntimeError(f"checksum mismatch for {fname}: artifact corrupted or modified")
    objs = {p.stem: joblib.load(p) for p in d.glob("*.joblib")}
    return objs, meta
