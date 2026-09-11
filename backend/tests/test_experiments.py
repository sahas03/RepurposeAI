import uuid


def test_create_experiment(client, project, researcher):
    resp = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Test Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["status"] == "DRAFT"
    assert body["progress"] == 0


def test_start_experiment_runs_to_completion_in_eager_mode(client, project, researcher):
    create = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Eager Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    experiment_id = create.json()["data"]["id"]

    resp = client.post(f"/api/v1/experiments/{experiment_id}/start", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "COMPLETED"


def test_experiment_status_endpoint(client, project, researcher):
    create = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Status Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    experiment_id = create.json()["data"]["id"]

    resp = client.get(f"/api/v1/experiments/{experiment_id}/status", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "DRAFT"


def test_drug_repurposing_experiment_produces_results(client, project, researcher, seeded_biotech):
    disease_id = str(seeded_biotech["disease"].id)
    create = client.post(
        "/api/v1/experiments",
        json={
            "project_id": project["id"], "name": "Repurposing Experiment", "experiment_type": "drug_repurposing",
            "parameters": {"disease_id": disease_id, "top_k": 5},
        },
        headers=researcher["headers"],
    )
    experiment_id = create.json()["data"]["id"]

    start_resp = client.post(f"/api/v1/experiments/{experiment_id}/start", headers=researcher["headers"])
    assert start_resp.status_code == 200
    assert start_resp.json()["data"]["status"] == "COMPLETED"

    results = client.get(f"/api/v1/experiments/{experiment_id}/results", headers=researcher["headers"])
    assert results.status_code == 200
    body = results.json()["data"]
    assert len(body["analyses"]) == 1
    assert len(body["predictions"]) >= 1
    prediction = body["predictions"][0]
    assert prediction["drug"]["name"] == seeded_biotech["drug"].name
    assert 0.0 <= prediction["confidence"] <= 1.0
    assert "reasons" in prediction["explanation"]


def test_cancel_queued_experiment(client, project, researcher, db):
    from app.models.experiment import Experiment
    from app.core.constants import ExperimentStatus

    create = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Cancel Me", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    experiment_id = create.json()["data"]["id"]

    # Force it into QUEUED directly - under CELERY_TASK_ALWAYS_EAGER, calling
    # /start would run the task synchronously to completion before we could cancel it.
    exp = db.get(Experiment, uuid.UUID(experiment_id))
    exp.status = ExperimentStatus.QUEUED.value
    db.commit()

    resp = client.post(f"/api/v1/experiments/{experiment_id}/cancel", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CANCELLED"


def test_cancel_draft_experiment_rejected(client, project, researcher):
    create = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Draft Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    )
    experiment_id = create.json()["data"]["id"]

    resp = client.post(f"/api/v1/experiments/{experiment_id}/cancel", headers=researcher["headers"])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EXPERIMENT_NOT_CANCELLABLE"
