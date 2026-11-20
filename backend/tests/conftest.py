import sys
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("TREXO_OWNER_PASSCODE", "phase-b-test-owner")
os.environ.pop("TREXO_OWNER_PASSCODE_HASH", None)
os.environ.setdefault("TREXO_ADMIN_TOKEN", "phase-b-test-admin")

from trexo_api.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "test.db"
    app = create_app(db)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    resp = client.post("/api/v1/auth/login", json={"password": "phase-b-test-owner"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture(scope="session")
def products(client, auth):
    resp = client.get("/api/v1/store/products", headers=auth)
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture()
def ml_history():
    rows = []
    for i in range(120):
        if i % 3 == 0:
            continue
        day = f"2011-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        rows.append({"date": day, "quantity": 2 + (i % 4), "unit_price": 3.5, "invoice_no": f"INV{i}"})
    return rows
