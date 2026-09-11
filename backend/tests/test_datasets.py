import io


def _upload_csv(client, project, researcher, content: bytes = b"gene,sample_1,sample_2\nTP53,1.1,2.2\nBRCA1,3.3,4.4\n"):
    files = {"file": ("demo.csv", io.BytesIO(content), "text/csv")}
    data = {"project_id": project["id"], "name": "Demo dataset"}
    return client.post("/api/v1/datasets/upload", data=data, files=files, headers=researcher["headers"])


def test_upload_dataset(client, project, researcher):
    resp = _upload_csv(client, project, researcher)
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["status"] == "VALID"
    assert body["row_count"] == 2
    assert body["column_count"] == 3


def test_upload_rejects_unsupported_extension(client, project, researcher):
    files = {"file": ("malware.exe", io.BytesIO(b"not a real dataset"), "application/octet-stream")}
    data = {"project_id": project["id"], "name": "Bad file"}
    resp = client.post("/api/v1/datasets/upload", data=data, files=files, headers=researcher["headers"])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_dataset_preview(client, project, researcher):
    upload = _upload_csv(client, project, researcher)
    dataset_id = upload.json()["data"]["id"]

    resp = client.get(f"/api/v1/datasets/{dataset_id}/preview", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["columns"] == ["gene", "sample_1", "sample_2"]
    assert len(body["rows"]) == 2


def test_dataset_metadata(client, project, researcher):
    upload = _upload_csv(client, project, researcher)
    dataset_id = upload.json()["data"]["id"]

    resp = client.get(f"/api/v1/datasets/{dataset_id}/metadata", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["row_count"] == 2
    assert body["quality_score"] is not None


def test_dataset_validate_endpoint(client, project, researcher):
    upload = _upload_csv(client, project, researcher)
    dataset_id = upload.json()["data"]["id"]

    resp = client.post(f"/api/v1/datasets/{dataset_id}/validate", headers=researcher["headers"])
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["is_valid"] is True
    assert body["status"] == "VALID"


def test_delete_dataset(client, project, researcher):
    upload = _upload_csv(client, project, researcher)
    dataset_id = upload.json()["data"]["id"]

    resp = client.delete(f"/api/v1/datasets/{dataset_id}", headers=researcher["headers"])
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/datasets/{dataset_id}", headers=researcher["headers"])
    assert resp.status_code == 404
