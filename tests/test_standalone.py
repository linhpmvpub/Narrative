from fastapi.testclient import TestClient
from test_product import draft

from engine.api import app
from engine.api.accounts import provision


def test_standalone_shell_and_explicit_demo_only(db):
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Narrative" in response.text
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"
        sample = client.get("/assets/demo.json").json()
        assert sample["is_synthetic"] is True
        assert sample["card"]["delivery_status"] == "disabled"
        assert client.get("/assets/__init__.py").status_code == 404
        script = client.get("/assets/app.js").text
        assert "innerHTML" not in script and "localStorage" not in script


def test_custom_narrative_list_is_owner_only(db):
    _, token = provision(db, "same-tenant")
    _, other = provision(db, "same-tenant")
    headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "create"}
    with TestClient(app) as client:
        assert client.get("/api/v0/narratives").status_code == 401
        created = client.post("/api/v0/narratives", headers=headers, json=draft())
        assert created.status_code == 200
        mine = client.get("/api/v0/narratives", headers=headers).json()["items"]
        theirs = client.get(
            "/api/v0/narratives", headers={"Authorization": "Bearer " + other}
        ).json()["items"]
        assert len(mine) == 1 and theirs == []
        assert mine[0]["id"] == created.json()["id"]
        assert mine[0]["version"] == 1
