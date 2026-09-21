def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_openapi_is_public(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "AIGC Studio Spine"
    assert "/api/projects" in body["paths"]


def test_api_requires_token(client):
    response = client.get("/api/projects")
    assert response.status_code == 401


def test_wrong_token_is_rejected(client):
    response = client.get("/api/projects", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_me_and_default_org(client, auth):
    me = client.get("/api/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["auth_mode"] == "local-dev"
    assert me.json()["sso"] == "later"
    orgs = client.get("/api/orgs", headers=auth)
    assert orgs.status_code == 200
    assert len(orgs.json()) == 1
    assert "local" in orgs.json()[0]["name"].lower()
