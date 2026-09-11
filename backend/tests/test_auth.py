from tests.conftest import unique_email


def test_register_creates_user(client):
    email = unique_email("register")
    resp = client.post("/api/v1/auth/register", json={"name": "New User", "email": email, "password": "SecurePass123!", "role": "viewer"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == email
    assert body["data"]["role"] == "viewer"
    assert "password" not in body["data"]


def test_register_duplicate_email_conflicts(client):
    email = unique_email("dup")
    payload = {"name": "Dup User", "email": email, "password": "SecurePass123!", "role": "viewer"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_success_returns_tokens(client):
    email = unique_email("login")
    client.post("/api/v1/auth/register", json={"name": "Login User", "email": email, "password": "SecurePass123!", "role": "viewer"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePass123!"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_login_invalid_password_rejected(client):
    email = unique_email("badlogin")
    client.post("/api/v1/auth/register", json={"name": "Bad Login", "email": email, "password": "SecurePass123!", "role": "viewer"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_refresh_token_issues_new_access_token(client):
    email = unique_email("refresh")
    client.post("/api/v1/auth/register", json={"name": "Refresh User", "email": email, "password": "SecurePass123!", "role": "viewer"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePass123!"}).json()["data"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert new_tokens["access_token"] != login["access_token"]


def test_get_me_requires_auth(client, researcher):
    resp = client.get("/api/v1/auth/me", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == researcher["email"]

    resp_unauth = client.get("/api/v1/auth/me")
    assert resp_unauth.status_code == 401


def test_update_me_changes_name(client, researcher):
    resp = client.put("/api/v1/auth/me", json={"name": "Updated Name"}, headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Updated Name"


def test_logout_revokes_refresh_token(client):
    email = unique_email("logout")
    client.post("/api/v1/auth/register", json={"name": "Logout User", "email": email, "password": "SecurePass123!", "role": "viewer"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePass123!"}).json()["data"]
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    resp = client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert resp.status_code == 200

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_REVOKED"
