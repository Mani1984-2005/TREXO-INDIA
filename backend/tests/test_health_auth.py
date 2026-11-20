from __future__ import annotations

import base64
import hashlib


def test_livez(client):
    assert client.get("/livez").status_code == 200


def test_health_reports_models(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert body["models"]["status"] in {"OK", "ok", "unavailable"}


def test_root_metadata(client):
    body = client.get("/").json()
    assert body["service"] == "trexo-india-api"
    assert body["health"] == "/api/v1/health"


def test_auth_required(client):
    assert client.get("/api/v1/store/products").status_code == 401


def test_auth_rejects_bad_token(client):
    resp = client.get("/api/v1/store/products", headers={"Authorization": "Bearer nope.nope"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] in {"INVALID_TOKEN", "AUTH_REQUIRED"}


def test_auth_rejects_expired_token(client):
    from trexo_api.security import create_token

    token = create_token("owner", ttl=-1)
    response = client.get(
        "/api/v1/store/products", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401


def test_login_returns_usable_bearer_token(client):
    response = client.post(
        "/api/v1/auth/login", json={"password": "phase-b-test-owner"}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["tokenType"] == "bearer"
    assert result["expiresIn"] > 0
    assert result["token"]

    protected = client.get(
        "/api/v1/store/products",
        headers={"Authorization": f"Bearer {result['token']}"},
    )
    assert protected.status_code == 200


def test_login_accepts_configured_pbkdf2_hash(client, monkeypatch):
    from trexo_api import security

    password = "hash-path-test-only"
    salt = b"phase-b-auth-test-salt"
    iterations = 10_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    passcode_hash = f"pbkdf2_sha256${iterations}${encode(salt)}${encode(digest)}"
    monkeypatch.setattr(security, "OWNER_PASSCODE_HASH", passcode_hash)
    monkeypatch.setattr(security, "OWNER_PASSCODE", None)

    response = client.post("/api/v1/auth/login", json={"password": password})
    assert response.status_code == 200
    assert response.json()["tokenType"] == "bearer"

    wrong = client.post(
        "/api/v1/auth/login", json={"password": "not-the-test-password"}
    )
    assert wrong.status_code == 401


def test_removed_universal_password_is_not_accepted(client):
    resp = client.post("/api/v1/auth/login", json={"password": "123456789"})
    assert resp.status_code == 401


def test_login_validation(client):
    assert client.post("/api/v1/auth/login", json={}).status_code == 422


def test_models_listing(client, auth):
    resp = client.get("/api/v1/models", headers=auth)
    assert resp.status_code == 200
    kinds = {m["kind"] for m in resp.json()}
    assert {"dead_stock", "forecasting", "movement", "pricing", "bundles"}.issubset(kinds)


def test_model_kind_not_found(client, auth):
    resp = client.get("/api/v1/models/not-a-model", headers=auth)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "MODEL_KIND_NOT_FOUND"


def test_admin_endpoint_disabled_without_token(client, auth):
    resp = client.post(
        "/api/v1/models/dead_stock/activate", json={"version": "x"}, headers=auth
    )
    assert resp.status_code in {403, 503}
    assert resp.json()["error"]["code"] in {"ADMIN_DISABLED", "ADMIN_FORBIDDEN"}
