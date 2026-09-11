"""Global search across biotech entities and the user's own research objects."""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.compound import Compound
from app.models.dataset import Dataset
from app.models.disease import Disease
from app.models.drug import Drug
from app.models.experiment import Experiment
from app.models.gene import Gene
from app.models.project import Project
from app.models.user import User

RESULTS_PER_CATEGORY = 8


def global_search(db: Session, user: User, query: str) -> dict:
    like = f"%{query}%"
    is_admin = user.role.name == "admin"

    drugs = db.scalars(
        select(Drug).where(or_(Drug.name.ilike(like), Drug.generic_name.ilike(like))).limit(RESULTS_PER_CATEGORY)
    ).all()
    diseases = db.scalars(
        select(Disease).where(or_(Disease.name.ilike(like), Disease.description.ilike(like))).limit(RESULTS_PER_CATEGORY)
    ).all()
    genes = db.scalars(
        select(Gene).where(or_(Gene.symbol.ilike(like), Gene.name.ilike(like))).limit(RESULTS_PER_CATEGORY)
    ).all()
    compounds = db.scalars(select(Compound).where(Compound.name.ilike(like)).limit(RESULTS_PER_CATEGORY)).all()

    project_stmt = select(Project).where(Project.name.ilike(like))
    if not is_admin:
        project_stmt = project_stmt.where(Project.owner_id == user.id)
    projects = db.scalars(project_stmt.limit(RESULTS_PER_CATEGORY)).all()

    experiment_stmt = select(Experiment).where(Experiment.name.ilike(like))
    if not is_admin:
        experiment_stmt = experiment_stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    experiments = db.scalars(experiment_stmt.limit(RESULTS_PER_CATEGORY)).all()

    dataset_stmt = select(Dataset).where(Dataset.name.ilike(like))
    if not is_admin:
        dataset_stmt = dataset_stmt.join(Project, Project.id == Dataset.project_id).where(Project.owner_id == user.id)
    datasets = db.scalars(dataset_stmt.limit(RESULTS_PER_CATEGORY)).all()

    results = {
        "drugs": [{"id": str(d.id), "name": d.name, "drug_class": d.drug_class} for d in drugs],
        "diseases": [{"id": str(d.id), "name": d.name, "category": d.category} for d in diseases],
        "genes": [{"id": str(g.id), "symbol": g.symbol, "name": g.name} for g in genes],
        "compounds": [{"id": str(c.id), "name": c.name} for c in compounds],
        "projects": [{"id": str(p.id), "name": p.name, "status": p.status} for p in projects],
        "experiments": [{"id": str(e.id), "name": e.name, "status": e.status} for e in experiments],
        "datasets": [{"id": str(d.id), "name": d.name, "status": d.status} for d in datasets],
    }
    total = sum(len(v) for v in results.values())
    return {"query": query, "results": results, "total_results": total}
