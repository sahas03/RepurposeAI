import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.gene import GeneOut
from app.services import gene_service

router = APIRouter(prefix="/genes", tags=["Genes"])


@router.get("", summary="List/search genes")
def list_genes(
    page: int = 1, page_size: int = 20, search: str | None = None, organism: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("gene:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = gene_service.list_genes(db, params, search, organism)
    return {"success": True, "data": result}


@router.get("/{gene_id}", summary="Get a gene by id")
def get_gene(gene_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("gene:read"))):
    gene = gene_service.get_gene_or_404(db, gene_id)
    return {"success": True, "data": GeneOut.model_validate(gene)}
