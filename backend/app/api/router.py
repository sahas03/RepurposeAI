from fastapi import APIRouter

from app.api.v1 import (
    analyses,
    analytics,
    audit,
    auth,
    compounds,
    dashboard,
    datasets,
    diseases,
    drugs,
    experiments,
    genes,
    health,
    interactions,
    notifications,
    predictions,
    projects,
    recommendations,
    search,
    targets,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(experiments.router)
api_router.include_router(datasets.router)
api_router.include_router(drugs.router)
api_router.include_router(diseases.router)
api_router.include_router(genes.router)
api_router.include_router(targets.router)
api_router.include_router(compounds.router)
api_router.include_router(interactions.router)
api_router.include_router(analyses.router)
api_router.include_router(predictions.repurposing_router)
api_router.include_router(predictions.predictions_router)
api_router.include_router(recommendations.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router)
api_router.include_router(audit.router)
