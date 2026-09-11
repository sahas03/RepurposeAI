"""
Test configuration.

Environment variables MUST be set before any `app.*` module is imported,
since app.core.config.settings is a module-level singleton bound at import
time. This makes the whole app (including Celery tasks, which use their own
DB session via app.db.database.SessionLocal rather than a FastAPI dependency)
consistently point at one shared, disposable SQLite test database, with
Celery running in eager (synchronous, in-process) mode so async pipelines are
exercised for real within each test.
"""
import os
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
_TEST_DB_PATH = _TEST_DIR / "test_repurpose.db"
_TEST_UPLOADS_DIR = _TEST_DIR / "_test_uploads"

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["JWT_SECRET"] = "test-only-secret-key-not-for-production-use-12345"
os.environ["STORAGE_TYPE"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = str(_TEST_UPLOADS_DIR)
os.environ["ENVIRONMENT"] = "testing"
os.environ["CORS_ORIGINS"] = "*"
os.environ["LOG_LEVEL"] = "WARNING"

import shutil  # noqa: E402
import uuid  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    shutil.rmtree(_TEST_UPLOADS_DIR, ignore_errors=True)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    shutil.rmtree(_TEST_UPLOADS_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


def register_and_login(client: TestClient, role: str = "researcher", name: str = "Test User") -> dict:
    email = unique_email(role)
    password = "TestPass123!"
    resp = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": password, "role": role})
    assert resp.status_code == 201, resp.text

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()["data"]
    return {
        "email": email,
        "password": password,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest.fixture()
def researcher(client):
    return register_and_login(client, role="researcher", name="Researcher User")


@pytest.fixture()
def viewer(client):
    return register_and_login(client, role="viewer", name="Viewer User")


@pytest.fixture()
def admin(client, db):
    from app.core.constants import RoleName
    from app.services.auth_service import get_or_create_role
    from app.models.user import User
    from app.core.security import hash_password

    role = get_or_create_role(db, RoleName.ADMIN.value)
    email = unique_email("admin")
    password = "AdminPass123!"
    user = User(name="Admin User", email=email, password_hash=hash_password(password), role_id=role.id, is_active=True)
    db.add(user)
    db.commit()

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()["data"]
    return {"email": email, "password": password, "headers": {"Authorization": f"Bearer {tokens['access_token']}"}}


@pytest.fixture()
def project(client, researcher):
    resp = client.post("/api/v1/projects", json={"name": "Test Project", "description": "A test project"}, headers=researcher["headers"])
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.fixture()
def seeded_biotech(db):
    """Minimal biotech fixture data (one disease with associated genes, one drug with a target hitting those genes)."""
    from app.models.disease import Disease
    from app.models.drug import Drug
    from app.models.gene import Gene
    from app.models.interaction import Interaction
    from app.models.target import Target

    disease = Disease(name=f"Test Disease {uuid.uuid4().hex[:6]}", description="A test disease", category="Test")
    gene = Gene(symbol=f"TG{uuid.uuid4().hex[:4].upper()}", name="Test Gene", organism="Homo sapiens")
    drug = Drug(name=f"TestDrug{uuid.uuid4().hex[:6]}", generic_name="test compound", drug_class="Test class", mechanism="Test mechanism")
    db.add_all([disease, gene, drug])
    db.flush()

    target = Target(name=f"{gene.symbol} target", target_type="protein", gene_id=gene.id)
    db.add(target)
    db.flush()

    db.add_all([
        Interaction(
            source_entity=f"gene:{gene.symbol}", target_entity=f"disease:{disease.name}",
            source_type="gene", source_id=str(gene.id), target_type="disease", target_id=str(disease.id),
            interaction_type="gene_disease", confidence_score=0.9, evidence={}, extra_metadata={},
        ),
        Interaction(
            source_entity=f"drug:{drug.name}", target_entity=f"target:{target.name}",
            source_type="drug", source_id=str(drug.id), target_type="target", target_id=str(target.id),
            interaction_type="drug_target", confidence_score=0.85, evidence={}, extra_metadata={},
        ),
    ])
    db.commit()
    return {"disease": disease, "gene": gene, "drug": drug, "target": target}
