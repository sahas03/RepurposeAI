def test_list_and_get_drug(client, researcher, seeded_biotech):
    resp = client.get("/api/v1/drugs?search=" + seeded_biotech["drug"].name, headers=researcher["headers"])
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert any(d["name"] == seeded_biotech["drug"].name for d in items)

    drug_id = seeded_biotech["drug"].id
    resp = client.get(f"/api/v1/drugs/{drug_id}", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == str(drug_id)


def test_get_disease_profile(client, researcher, seeded_biotech):
    disease_id = seeded_biotech["disease"].id
    resp = client.get(f"/api/v1/diseases/{disease_id}", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["disease"]["id"] == str(disease_id)
    assert body["associated_gene_count"] >= 1
    assert seeded_biotech["gene"].symbol in body["associated_genes"]


def test_list_genes_targets_compounds(client, researcher, seeded_biotech):
    resp = client.get("/api/v1/genes?search=" + seeded_biotech["gene"].symbol, headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    resp = client.get(f"/api/v1/targets?gene_id={seeded_biotech['gene'].id}", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    resp = client.get("/api/v1/compounds", headers=researcher["headers"])
    assert resp.status_code == 200


def test_list_interactions_filters(client, researcher, seeded_biotech):
    resp = client.get("/api/v1/interactions?interaction_type=drug_target&min_confidence=0.5", headers=researcher["headers"])
    assert resp.status_code == 200
    for item in resp.json()["data"]["items"]:
        assert item["interaction_type"] == "drug_target"
        assert item["confidence_score"] >= 0.5


def test_global_search_returns_grouped_results(client, researcher, project, seeded_biotech):
    resp = client.get(f"/api/v1/search?q={seeded_biotech['drug'].name}", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["query"] == seeded_biotech["drug"].name
    assert any(d["name"] == seeded_biotech["drug"].name for d in body["results"]["drugs"])


def test_generate_and_list_recommendations(client, researcher, project, db):
    from app.models.dataset import Dataset
    from app.core.constants import DatasetStatus
    import uuid as uuid_mod

    # An INVALID dataset is one of the recommendation triggers.
    db.add(Dataset(
        project_id=uuid_mod.UUID(project["id"]), name="Broken dataset", file_name="broken.csv",
        file_type="csv", file_size=10, storage_path="nowhere", status=DatasetStatus.INVALID.value,
    ))
    db.commit()

    gen_resp = client.post("/api/v1/recommendations/generate", json={"project_id": project["id"]}, headers=researcher["headers"])
    assert gen_resp.status_code == 200
    recs = gen_resp.json()["data"]
    assert any(r["recommendation_type"] == "dataset_attention" for r in recs)

    list_resp = client.get("/api/v1/recommendations", headers=researcher["headers"])
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["total"] >= 1

    rec_id = recs[0]["id"]
    dismiss_resp = client.post(f"/api/v1/recommendations/{rec_id}/dismiss", headers=researcher["headers"])
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["data"]["status"] == "DISMISSED"


def test_notifications_list_and_mark_read(client, researcher, project, db):
    from app.services.notification_service import create_notification
    from app.core.constants import NotificationType
    import uuid as uuid_mod

    notification = create_notification(
        db, uuid_mod.UUID(_current_user_id(db, researcher)),
        "Test notice", "A test notification", NotificationType.SYSTEM,
    )
    db.commit()

    resp = client.get("/api/v1/notifications", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    resp = client.get("/api/v1/notifications/unread", headers=researcher["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["unread_count"] >= 1

    mark_resp = client.put(f"/api/v1/notifications/{notification.id}/read", headers=researcher["headers"])
    assert mark_resp.status_code == 200
    assert mark_resp.json()["data"]["read"] is True

    mark_all_resp = client.put("/api/v1/notifications/read-all", headers=researcher["headers"])
    assert mark_all_resp.status_code == 200


def _current_user_id(db, auth_ctx):
    from app.models.user import User
    user = db.query(User).filter(User.email == auth_ctx["email"]).first()
    return str(user.id)
