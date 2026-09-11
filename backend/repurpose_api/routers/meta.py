"""Service metadata and the dataset catalogue."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import bridge, caching, config, datasets, precompute
from ..schemas import DatasetDescriptor

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health", summary="Liveness and capability report")
def health() -> dict:
    """What this instance can actually do right now.

    Worth checking before a demo: it reports whether the optional cheminformatics
    and enrichment libraries are present and which datasets have their files.
    """
    return {
        "status": "ok",
        "version": config.API_VERSION,
        "datasets": [d.id for d in datasets.list_descriptors()],
        "unavailableDatasets": [
            d.id for d in datasets.list_descriptors(include_unavailable=True) if not d.available
        ],
        "capabilities": {
            "rdkitAvailable": bridge.RDKIT_AVAILABLE,
            "gseapyAvailable": bridge.GSEAPY_AVAILABLE,
            "safetyTableLoaded": datasets.load_safety_table() is not None,
            "staleFallbackEnabled": config.STALE_FALLBACK_ENABLED,
        },
        "cache": caching.stats(),
        "precomputed": precompute.available(),
    }


@router.get("/datasets", response_model=list[DatasetDescriptor], summary="Dataset descriptors")
def list_datasets(
    include_unavailable: bool = Query(
        False,
        alias="includeUnavailable",
        description="Also list registered datasets whose CSV files are not present yet.",
    ),
) -> list[DatasetDescriptor]:
    """Ids, labels, provenance and the disclosure text shown verbatim in the UI."""
    return datasets.list_descriptors(include_unavailable=include_unavailable)
