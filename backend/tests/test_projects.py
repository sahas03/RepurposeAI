def test_create_project(client, researcher):
    resp = client.post("/api/v1/projects", json={"name": "Cancer Research", "description": "desc"}, headers=researcher["headers"])
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["name"] == "Cancer Research"
    assert body["status"] == "ACTIVE"


def test_list_projects_paginated(client, researcher):
    for i in range(3):
        client.post("/api/v1/projects", json={"name": f"Project {i}"}, headers=researcher["headers"])

    resp = client.get("/api/v1/projects?page=1&page_size=2", headers=researcher["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] >= 3


def test_get_project_by_id(client, project, researcher):
    resp = client.get(f"/api/v1/projects/{project['id']}", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == project["id"]


def test_get_nonexistent_project_404(client, researcher):
    resp = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=researcher["headers"])
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_update_project(client, project, researcher):
    resp = client.put(f"/api/v1/projects/{project['id']}", json={"name": "Renamed", "status": "COMPLETED"}, headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["name"] == "Renamed"
    assert body["status"] == "COMPLETED"


def test_delete_project(client, project, researcher):
    resp = client.delete(f"/api/v1/projects/{project['id']}", headers=researcher["headers"])
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/projects/{project['id']}", headers=researcher["headers"])
    assert resp.status_code == 404


def test_project_summary(client, project, researcher):
    resp = client.get(f"/api/v1/projects/{project['id']}/summary", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["experiment_count"] == 0
    assert body["project"]["id"] == project["id"]


def test_other_user_cannot_access_project(client, project, viewer):
    resp = client.get(f"/api/v1/projects/{project['id']}", headers=viewer["headers"])
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PROJECT_ACCESS_DENIED"
