def test_dashboard_overview_reflects_created_project(client, project, researcher):
    resp = client.get("/api/v1/dashboard/overview", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total_projects"] >= 1
    assert set(body.keys()) == {
        "total_projects", "active_projects", "total_experiments", "running_experiments",
        "completed_experiments", "failed_experiments", "total_datasets", "analyses_running",
        "predictions_generated", "high_confidence_candidates",
    }


def test_dashboard_system_status(client, researcher):
    resp = client.get("/api/v1/dashboard/system-status", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["database"] == "healthy"


def test_dashboard_recent_experiments(client, project, researcher):
    client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Dashboard Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    resp = client.get("/api/v1/dashboard/recent-experiments", headers=researcher["headers"])
    assert resp.status_code == 200
    assert any(e["name"] == "Dashboard Experiment" for e in resp.json()["data"])


def test_analytics_experiments_range(client, researcher):
    resp = client.get("/api/v1/analytics/experiments?range=30d", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["range"] == "30d"
    assert len(body["labels"]) == len(body["series"]["experiments_created"])


def test_analytics_predictions_range(client, researcher):
    resp = client.get("/api/v1/analytics/predictions?range=7d", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["range"] == "7d"
