def test_repurposing_run_generates_ranked_predictions(client, project, researcher, seeded_biotech):
    disease_id = str(seeded_biotech["disease"].id)
    resp = client.post(
        "/api/v1/repurposing/run",
        json={"disease_id": disease_id, "project_id": project["id"], "parameters": {"top_k": 5}},
        headers=researcher["headers"],
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]
    # CELERY_TASK_ALWAYS_EAGER means this has already run synchronously.
    assert resp.json()["data"]["status"] in ("QUEUED", "COMPLETED")

    status_resp = client.get(f"/api/v1/repurposing/{job_id}", headers=researcher["headers"])
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "COMPLETED"

    results_resp = client.get(f"/api/v1/repurposing/{job_id}/results", headers=researcher["headers"])
    assert results_resp.status_code == 200
    body = results_resp.json()["data"]
    assert body["status"] == "COMPLETED"
    assert len(body["predictions"]) >= 1

    predictions = body["predictions"]
    ranks = [p["rank"] for p in predictions]
    assert ranks == sorted(ranks)
    assert predictions[0]["drug"]["name"] == seeded_biotech["drug"].name
    for p in predictions:
        assert 0.0 <= p["score"] <= 1.0
        assert 0.0 <= p["confidence"] <= 1.0
        assert p["explanation"]["disclaimer"]


def test_repurposing_run_rejects_disease_with_no_gene_data(client, project, researcher, db):
    from app.models.disease import Disease

    disease = Disease(name="Isolated Disease", description="No gene associations")
    db.add(disease)
    db.commit()

    resp = client.post(
        "/api/v1/repurposing/run",
        json={"disease_id": str(disease.id), "project_id": project["id"], "parameters": {}},
        headers=researcher["headers"],
    )
    # Runs eagerly; the job itself records the failure rather than the HTTP call raising.
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]

    status_resp = client.get(f"/api/v1/repurposing/{job_id}", headers=researcher["headers"])
    assert status_resp.json()["data"]["status"] == "FAILED"
    assert "gene" in status_resp.json()["data"]["error"].lower()


def test_list_predictions_filters_by_min_confidence(client, project, researcher, seeded_biotech):
    disease_id = str(seeded_biotech["disease"].id)
    run = client.post(
        "/api/v1/repurposing/run",
        json={"disease_id": disease_id, "project_id": project["id"], "parameters": {"top_k": 5}},
        headers=researcher["headers"],
    )
    job_id = run.json()["data"]["job_id"]
    client.get(f"/api/v1/repurposing/{job_id}", headers=researcher["headers"])

    resp = client.get(f"/api/v1/predictions?project_id={project['id']}&min_confidence=0", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    resp_impossible = client.get(f"/api/v1/predictions?project_id={project['id']}&min_confidence=1.01", headers=researcher["headers"])
    assert resp_impossible.status_code == 200
    assert resp_impossible.json()["data"]["total"] == 0
