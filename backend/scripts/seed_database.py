#!/usr/bin/env python
"""
Seeds the database with a rich DEMO/SYNTHETIC dataset so the frontend has
something realistic to render immediately: 20+ projects, 100+ drugs, 50+
diseases, 100+ genes/targets, 200+ interactions, 100+ predictions (computed by
the real AI pipeline), 30+ notifications, plus datasets, experiments,
analyses, recommendations, and demo users across every role.

Usage:
    python scripts/seed_database.py [--reset]

--reset drops and recreates all tables first (destructive - local/dev only).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.models.drug import Drug  # noqa: E402
from scripts import generate_demo_data as gen  # noqa: E402
from scripts.create_admin import create_admin  # noqa: E402


def already_seeded(db) -> bool:
    return db.query(Drug).first() is not None


def run(reset: bool) -> None:
    if reset:
        print("Dropping and recreating all tables...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    start = time.time()
    try:
        if not reset and already_seeded(db):
            print("Database already contains demo data. Re-run with --reset to wipe and reseed.")
            return

        print("Creating admin user...")
        create_admin_inline(db)

        print("Seeding demo users...")
        users = gen.seed_users(db)
        db.commit()

        print("Seeding biotech reference entities (drugs, diseases, genes, targets, compounds, interactions)...")
        entities = gen.seed_biotech_entities(db)
        db.commit()

        print("Seeding projects...")
        projects = gen.seed_projects(db, users, entities["diseases"])
        db.commit()

        print("Seeding datasets...")
        datasets = gen.seed_datasets(db, projects, entities["genes"])
        db.commit()

        print("Seeding experiments and running the real repurposing pipeline for demo predictions...")
        exp_result = gen.seed_experiments_and_predictions(db, projects, entities["diseases"], datasets)
        db.commit()

        print("Seeding notifications...")
        notification_count = gen.seed_notifications(db, users)
        db.commit()

        print("Generating rule-based recommendations from the seeded data...")
        recommendation_count = gen.seed_recommendations(db, users)
        db.commit()

        elapsed = time.time() - start
        print("\n" + "=" * 60)
        print(f"Seed complete in {elapsed:.1f}s")
        print("=" * 60)
        print(f"  Users:            {len(users) + 1} (including admin)")
        print(f"  Drugs:            {len(entities['drugs'])}")
        print(f"  Diseases:         {len(entities['diseases'])}")
        print(f"  Genes:            {len(entities['genes'])}")
        print(f"  Targets:          {len(entities['targets'])}")
        print(f"  Compounds:        {len(entities['compounds'])}")
        print(f"  Interactions:     {len(entities['interactions'])}")
        print(f"  Projects:         {len(projects)}")
        print(f"  Datasets:         {len(datasets)}")
        print(f"  Experiments:      {len(exp_result['experiments'])}")
        print(f"  Predictions:      {exp_result['prediction_count']}")
        print(f"  Notifications:    {notification_count}")
        print(f"  Recommendations:  {recommendation_count}")
        print("=" * 60)
        print("Demo login: any seeded user email (see USER_NAME_ROLES in generate_demo_data.py) / password 'Demo1234!'")
        print("Admin login: see .env FIRST_SUPERUSER_EMAIL / FIRST_SUPERUSER_PASSWORD")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_admin_inline(db) -> None:
    from app.core.config import settings
    from app.core.constants import RoleName
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.auth_service import get_or_create_role

    role = get_or_create_role(db, RoleName.ADMIN.value)
    existing = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL.lower()).first()
    if existing:
        return
    admin = User(
        name=settings.FIRST_SUPERUSER_NAME,
        email=settings.FIRST_SUPERUSER_EMAIL.lower(),
        password_hash=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with demo data.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding.")
    args = parser.parse_args()
    run(reset=args.reset)
