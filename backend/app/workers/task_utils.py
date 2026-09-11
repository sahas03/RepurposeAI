"""Shared helpers for Celery tasks: DB session scoping and consistent error handling."""
import logging
from contextlib import contextmanager

from app.db.database import SessionLocal

logger = logging.getLogger("app.workers")


@contextmanager
def task_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
