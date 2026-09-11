"""Query and summarize the Interaction graph (drug-target, gene-disease, etc)."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction


def get_entity_interactions(db: Session, entity_type: str, entity_id: uuid.UUID, limit: int = 50) -> list[Interaction]:
    stmt = (
        select(Interaction)
        .where(
            ((Interaction.source_type == entity_type) & (Interaction.source_id == str(entity_id)))
            | ((Interaction.target_type == entity_type) & (Interaction.target_id == str(entity_id)))
        )
        .order_by(Interaction.confidence_score.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def interaction_type_breakdown(db: Session) -> dict[str, int]:
    from sqlalchemy import func

    rows = db.execute(
        select(Interaction.interaction_type, func.count(Interaction.id)).group_by(Interaction.interaction_type)
    ).all()
    return {row[0]: row[1] for row in rows}
