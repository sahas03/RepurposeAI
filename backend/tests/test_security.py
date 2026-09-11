def test_protected_route_without_token_is_401(client):
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_protected_route_with_garbage_token_is_401(client):
    resp = client.get("/api/v1/projects", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_expired_style_malformed_token_is_401(client):
    # A syntactically-plausible but unsigned/invalid JWT should also be rejected.
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.invalidsignature"
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_jwt}"})
    assert resp.status_code == 401


def test_viewer_forbidden_from_admin_only_route(client, viewer):
    resp = client.get("/api/v1/audit-logs", headers=viewer["headers"])
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_ERROR"


def test_admin_can_access_admin_only_route(client, admin):
    resp = client.get("/api/v1/audit-logs", headers=admin["headers"])
    assert resp.status_code == 200


def test_viewer_cannot_write_projects(client, viewer):
    resp = client.post("/api/v1/projects", json={"name": "nope"}, headers=viewer["headers"])
    assert resp.status_code == 403


def test_viewer_cannot_access_another_users_project(client, project, viewer):
    resp = client.put(f"/api/v1/projects/{project['id']}", json={"name": "hijacked"}, headers=viewer["headers"])
    assert resp.status_code in (403, 404)


def test_404_error_envelope_shape(client, researcher):
    resp = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=researcher["headers"])
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert "code" in body["error"]
    assert "message" in body["error"]
