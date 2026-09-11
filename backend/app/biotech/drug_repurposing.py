"""
Drug repurposing orchestrator.

Ties together the biotech query layer (gene/target/evidence/compound
similarity) and the AI pipeline to produce ranked, explained drug candidates
for a given disease. This is the computational heart of PART 9 of the product
spec. Persistence of the resulting predictions is the caller's responsibility
(see app/services/prediction_service.py) so this module stays read-only and
easy to unit test.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.pipeline import RepurposingCandidate, RepurposingPipeline
from app.biotech.compound_similarity import compute_similarity_to_reference, get_reference_compounds_for_disease
from app.biotech.disease_analysis import get_disease_or_404
from app.biotech.evidence_scoring import gather_supporting_interactions
from app.biotech.gene_analysis import get_disease_associated_genes
from app.biotech.target_analysis import get_drug_targets, target_gene_symbols
from app.core.exceptions import ValidationAppError
from app.models.compound import Compound
from app.models.drug import Drug


def run_repurposing_analysis(db: Session, disease_id: uuid.UUID, top_k: int = 20) -> dict:
    # Step 1: input validation
    disease = get_disease_or_404(db, disease_id)

    # Step 2 + 3: preprocessing / feature source gathering
    disease_genes = get_disease_associated_genes(db, disease_id)
    disease_gene_symbols = {g.symbol for g in disease_genes}
    if not disease_gene_symbols:
        raise ValidationAppError(
            "This disease has no associated gene data in the platform yet, "
            "so repurposing candidates cannot be computed.",
            code="INSUFFICIENT_DISEASE_DATA",
        )

    reference_compounds = get_reference_compounds_for_disease(db, disease_id)

    drugs = db.scalars(select(Drug)).all()
    candidates: list[RepurposingCandidate] = []

    for drug in drugs:
        targets = get_drug_targets(db, drug.id)
        drug_gene_symbols = target_gene_symbols(targets, db)

        # Step 6: target overlap is only meaningful evidence-gathering-wise when
        # the drug actually shares biology with the disease.
        supporting = gather_supporting_interactions(
            db, drug.id, disease_id, target_ids=[t.id for t in targets]
        )

        compounds = list(db.scalars(select(Compound).where(Compound.drug_id == drug.id)).all())
        compound_similarity = compute_similarity_to_reference(compounds, reference_compounds)

        # Skip drugs with zero signal entirely - not a real repurposing candidate.
        if not drug_gene_symbols and not supporting and compound_similarity == 0:
            continue

        candidates.append(
            RepurposingCandidate(
                drug_id=str(drug.id),
                drug_name=drug.name,
                target_gene_symbols=drug_gene_symbols,
                target_count=len(targets),
                supporting_interactions=supporting,
                compound_similarity_score=compound_similarity,
            )
        )

    pipeline = RepurposingPipeline()
    results = pipeline.run(
        disease_name=disease.name,
        disease_gene_symbols=disease_gene_symbols,
        candidates=candidates,
        top_k=top_k,
    )

    return {
        "disease_id": str(disease_id),
        "disease_name": disease.name,
        "candidate_pool_size": len(candidates),
        "results": results,
    }
