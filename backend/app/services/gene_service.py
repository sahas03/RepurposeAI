import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.gene import Gene
from app.models.interaction import Interaction
from app.models.target import Target
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.gene import GeneOut, InteractionOut, TargetOut
from app.utils.pagination import paginate


def list_genes(db: Session, params: PaginationParams, search: str | None, organism: str | None) -> PaginatedResponse[GeneOut]:
    stmt = select(Gene)
    if search:
        stmt = stmt.where(or_(Gene.symbol.ilike(f"%{search}%"), Gene.name.ilike(f"%{search}%")))
    if organism:
        stmt = stmt.where(Gene.organism == organism)
    stmt = stmt.order_by(Gene.symbol.asc())
    return paginate(db, stmt, params, GeneOut)


def get_gene_or_404(db: Session, gene_id: uuid.UUID) -> Gene:
    gene = db.get(Gene, gene_id)
    if not gene:
        raise NotFoundError("Gene was not found", code="GENE_NOT_FOUND")
    return gene


def list_targets(db: Session, params: PaginationParams, search: str | None, target_type: str | None, gene_id: uuid.UUID | None) -> PaginatedResponse[TargetOut]:
    stmt = select(Target)
    if search:
        stmt = stmt.where(Target.name.ilike(f"%{search}%"))
    if target_type:
        stmt = stmt.where(Target.target_type == target_type)
    if gene_id:
        stmt = stmt.where(Target.gene_id == gene_id)
    stmt = stmt.order_by(Target.name.asc())
    return paginate(db, stmt, params, TargetOut)


def get_target_or_404(db: Session, target_id: uuid.UUID) -> Target:
    target = db.get(Target, target_id)
    if not target:
        raise NotFoundError("Target was not found", code="TARGET_NOT_FOUND")
    return target


def list_interactions(db: Session, params: PaginationParams, interaction_type: str | None, source_type: str | None, target_type: str | None, min_confidence: float | None) -> PaginatedResponse[InteractionOut]:
    stmt = select(Interaction)
    if interaction_type:
        stmt = stmt.where(Interaction.interaction_type == interaction_type)
    if source_type:
        stmt = stmt.where(Interaction.source_type == source_type)
    if target_type:
        stmt = stmt.where(Interaction.target_type == target_type)
    if min_confidence is not None:
        stmt = stmt.where(Interaction.confidence_score >= min_confidence)
    stmt = stmt.order_by(Interaction.confidence_score.desc())
    return paginate(db, stmt, params, InteractionOut)
