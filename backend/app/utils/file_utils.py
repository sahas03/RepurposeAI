"""
Storage adapter abstraction.

`get_storage()` returns a LocalStorage or S3Storage instance depending on
STORAGE_TYPE. Both implement the same tiny interface (save/read/delete/url) so
the rest of the app never needs to know which backend is active.
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import FileProcessingError


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, relative_path: str) -> str:
        """Persist bytes, returning the storage_path to record on the model."""

    @abstractmethod
    def read(self, storage_path: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        ...

    @abstractmethod
    def local_path(self, storage_path: str) -> str:
        """Return a filesystem path pandas/biopython can open directly."""


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, relative_path: str) -> str:
        full_path = self.base_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(relative_path)

    def read(self, storage_path: str) -> bytes:
        full_path = self.base_dir / storage_path
        if not full_path.exists():
            raise FileProcessingError("Stored file could not be found on disk", code="FILE_NOT_FOUND")
        return full_path.read_bytes()

    def delete(self, storage_path: str) -> None:
        full_path = self.base_dir / storage_path
        if full_path.exists():
            full_path.unlink()

    def local_path(self, storage_path: str) -> str:
        return str(self.base_dir / storage_path)


class S3Storage(StorageBackend):
    def __init__(self):
        import boto3

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def save(self, content: bytes, relative_path: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=relative_path, Body=content)
        return relative_path

    def read(self, storage_path: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=storage_path)
            return obj["Body"].read()
        except Exception as exc:
            raise FileProcessingError("Stored file could not be found in object storage", code="FILE_NOT_FOUND") from exc

    def delete(self, storage_path: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_path)

    def local_path(self, storage_path: str) -> str:
        """Download to a local temp file so pandas/biopython readers can open it."""
        tmp_dir = Path(settings.LOCAL_STORAGE_PATH) / "_s3_cache"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = tmp_dir / f"{uuid.uuid4().hex}_{Path(storage_path).name}"
        tmp_file.write_bytes(self.read(storage_path))
        return str(tmp_file)


_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance
    if settings.STORAGE_TYPE == "s3":
        _storage_instance = S3Storage()
    else:
        _storage_instance = LocalStorage(settings.LOCAL_STORAGE_PATH)
    return _storage_instance


def build_dataset_storage_key(project_id: str, dataset_id: str, file_name: str) -> str:
    safe_name = os.path.basename(file_name)
    return f"datasets/{project_id}/{dataset_id}/{safe_name}"
