"""
Compound similarity scoring using declared physicochemical properties.

A full cheminformatics stack (RDKit fingerprints, Tanimoto similarity) is the
natural upgrade path here; this module works purely off `Compound.properties`
and `Compound.molecular_weight` so it has zero extra system dependencies while
remaining architecturally swappable (see app/ai/similarity/similarity_model.py).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.similarity.similarity_model import SimilarityModel
from app.models.compound import Compound
from app.models.interaction import Interaction

PROPERTY_KEYS = ["logp", "h_bond_donors", "h_bond_acceptors", "polar_surface_area", "rotatable_bonds"]


def compound_feature_vector(compound: Compound) -> list[float]:
    props = compound.properties or {}
    return [compound.molecular_weight or 0.0] + [float(props.get(k, 0.0)) for k in PROPERTY_KEYS]


def get_reference_compounds_for_disease(db: Session, disease_id: uuid.UUID) -> list[Compound]:
    """Compounds belonging to drugs with an existing (demo) drug_disease link to this disease."""
    drug_ids = db.scalars(
        select(Interaction.source_id).where(
            Interaction.interaction_type == "drug_disease",
            Interaction.source_type == "drug",
            Interaction.target_type == "disease",
            Interaction.target_id == str(disease_id),
        )
    ).all()
    if not drug_ids:
        return []
    return list(db.scalars(select(Compound).where(Compound.drug_id.in_(drug_ids))).all())


def compute_similarity_to_reference(candidate_compounds: list[Compound], reference_compounds: list[Compound]) -> float:
    if not candidate_compounds or not reference_compounds:
        return 0.0
    sim = SimilarityModel()
    scores = []
    for candidate in candidate_compounds:
        cvec = compound_feature_vector(candidate)
        for reference in reference_compounds:
            rvec = compound_feature_vector(reference)
            scores.append(sim.cosine(cvec, rvec))
    return round(max(scores), 4) if scores else 0.0
