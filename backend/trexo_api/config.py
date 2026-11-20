"""Runtime configuration for the TREXO backend.

Secrets are never hardcoded.  ``TREXO_AUTH_SECRET`` must be supplied in any
real deployment; in local development a random secret is generated once and
kept in ``backend/data/.auth_secret`` (git-ignored) so tokens survive restarts.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = Path(os.environ.get("TREXO_DATA_DIR", BACKEND_DIR / "data"))
DB_PATH = Path(os.environ.get("TREXO_DB_PATH", DATA_DIR / "trexo.db"))

# Owner passcode.  No universal default is provided.  Production must set
# TREXO_OWNER_PASSCODE or, preferably, TREXO_OWNER_PASSCODE_HASH.
OWNER_PASSCODE = os.environ.get("TREXO_OWNER_PASSCODE")
OWNER_PASSCODE_HASH = os.environ.get("TREXO_OWNER_PASSCODE_HASH")
TOKEN_TTL_SECONDS = int(os.environ.get("TREXO_TOKEN_TTL_SECONDS", 60 * 60 * 12))

# Comma-separated list of allowed browser origins.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "TREXO_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# Model-management operations (activation / rollback) are disabled unless an
# explicit admin token is configured.
ADMIN_TOKEN = os.environ.get("TREXO_ADMIN_TOKEN", "")

MAX_ML_RECORDS = int(os.environ.get("TREXO_MAX_ML_RECORDS", 20000))
MAX_SALE_ITEMS = 100


def _load_auth_secret() -> str:
    env = os.environ.get("TREXO_AUTH_SECRET")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = DATA_DIR / ".auth_secret"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    generated = secrets.token_urlsafe(48)
    f.write_text(generated, encoding="utf-8")
    try:  # best effort on POSIX; no-op on Windows
        os.chmod(f, 0o600)
    except OSError:
        pass
    return generated


AUTH_SECRET = _load_auth_secret()
SERVICE_NAME = "trexo-india-api"
API_PREFIX = "/api/v1"
