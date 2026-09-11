import io


def test_run_dataset_quality_analysis(client, project, researcher):
    files = {"file": ("demo.csv", io.BytesIO(b"gene,sample_1\nTP53,1.1\nBRCA1,3.3\n"), "text/csv")}
    upload = client.post("/api/v1/datasets/upload", data={"project_id": project["id"], "name": "Analysis dataset"}, files=files, headers=researcher["headers"])
    dataset_id = upload.json()["data"]["id"]

    experiment = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "Analysis Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    ).json()["data"]

    run_resp = client.post(
        "/api/v1/analyses/run",
        json={"experiment_id": experiment["id"], "dataset_id": dataset_id, "analysis_type": "dataset_quality", "parameters": {}},
        headers=researcher["headers"],
    )
    assert run_resp.status_code == 202
    body = run_resp.json()["data"]
    # CELERY_TASK_ALWAYS_EAGER runs this synchronously before the response is returned.
    assert body["status"] == "COMPLETED"

    analysis_resp = client.get(f"/api/v1/analyses/{body['analysis_id']}", headers=researcher["headers"])
    assert analysis_resp.status_code == 200
    analysis = analysis_resp.json()["data"]
    assert analysis["status"] == "COMPLETED"
    assert analysis["results"]["row_count"] == 2


def test_analysis_without_dataset_fails_gracefully(client, project, researcher):
    experiment = client.post(
        "/api/v1/experiments",
        json={"project_id": project["id"], "name": "No Dataset Experiment", "experiment_type": "custom", "parameters": {}},
        headers=researcher["headers"],
    ).json()["data"]

    run_resp = client.post(
        "/api/v1/analyses/run",
        json={"experiment_id": experiment["id"], "analysis_type": "dataset_quality", "parameters": {}},
        headers=researcher["headers"],
    )
    body = run_resp.json()["data"]
    analysis = client.get(f"/api/v1/analyses/{body['analysis_id']}", headers=researcher["headers"]).json()["data"]
    assert analysis["status"] == "FAILED"
    assert analysis["error_message"]
