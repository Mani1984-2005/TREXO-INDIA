from __future__ import annotations


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


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"password": "wrong"})
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
