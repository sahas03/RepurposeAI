"""Target-centric queries: which targets a drug hits, and their associated genes."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gene import Gene
from app.models.interaction import Interaction
from app.models.target import Target


def get_drug_targets(db: Session, drug_id: uuid.UUID) -> list[Target]:
    target_ids = db.scalars(
        select(Interaction.target_id).where(
            Interaction.interaction_type == "drug_target",
            Interaction.source_type == "drug",
            Interaction.source_id == str(drug_id),
            Interaction.target_type == "target",
        )
    ).all()
    if not target_ids:
        return []
    return list(db.scalars(select(Target).where(Target.id.in_(target_ids))).all())


def target_gene_symbols(targets: list[Target], db: Session) -> set[str]:
    gene_ids = {t.gene_id for t in targets if t.gene_id}
    if not gene_ids:
        return set()
    genes = db.scalars(select(Gene).where(Gene.id.in_(gene_ids))).all()
    return {g.symbol for g in genes}


def target_overlap_ratio(drug_gene_symbols: set[str], disease_gene_symbols: set[str]) -> float:
    if not disease_gene_symbols:
        return 0.0
    return len(drug_gene_symbols & disease_gene_symbols) / len(disease_gene_symbols)
