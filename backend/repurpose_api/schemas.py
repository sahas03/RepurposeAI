"""
schemas.py
Response shapes, mirroring frontend/src/engine/types.ts field-for-field.

Every model below is camelCase on the wire (via a camel alias generator) and
snake_case in Python, so the existing frontend types need no changes: a
PipelineResult serialised here satisfies the PipelineResult interface the UI
already compiles against. Where a name differs from the TypeScript, that is a
bug in this file, not a licence for the frontend to adapt.

Cross-reference, TS -> here:
  ScoredDrug -> ScoredDrug          Candidate  -> Candidate
  RecoveryResult -> RecoveryResult  SyntheticCheck -> SyntheticCheck
  GeneContribution -> GeneContribution
  PipelineSettings -> PipelineSettings
  PipelineResult -> PipelineResult
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ScoringMethod = Literal["cosine", "cosine-fast", "wtcs"]
Provenance = Literal["synthetic", "real", "uploaded"]
NoveltyLabel = Literal["known hit (validation evidence)", "novel candidate"]
Direction = Literal["reversed by drug", "reinforced by drug (unwanted)"]

#: Verbatim from frontend/src/engine/run.ts METHOD_LABELS, so the HUD label the
#: UI shows for a run is produced by whoever actually ran it.
METHOD_LABELS: dict[str, str] = {
    "cosine": "Cosine similarity",
    "cosine-fast": "Cosine similarity, vectorised fast path",
    "wtcs": "Weighted Connectivity Score (WTCS)",
}

#: Stage ids, in order, from frontend/src/engine/run.ts STAGES.
STAGE_IDS = ("signature", "library", "reversal", "safety", "explain", "validation")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Weights(CamelModel):
    reversal: float = 0.6
    safety: float = 0.2
    novelty: float = 0.2


class PipelineSettings(CamelModel):
    """Mirrors PipelineSettings in types.ts. Defaults match the frontend's
    DEFAULT_SETTINGS in store/useApp.ts so a bare POST reproduces the UI's run."""

    dataset_id: str = "synthetic-benchmark"
    disease_name: str = "rheumatoid arthritis"
    method: ScoringMethod = "cosine-fast"
    display_top_n: int = Field(default=15, ge=1, le=1000)
    validation_top_k: int = Field(default=20, ge=1, le=1000)
    weights: Weights = Field(default_factory=Weights)

    #: WTCS only. True (the pipeline's own default) is the |z|-weighted GSEA
    #: enrichment of Subramanian et al. 2017. False is the unweighted KS score
    #: of Lamb et al. 2006 -- which is what the frontend's TypeScript port
    #: currently computes, bit-for-bit. Not part of types.ts; the UI ignores it.
    #: See the WTCS section of backend/README.md before changing the default.
    wtcs_weighted: bool = True


class DatasetDescriptor(CamelModel):
    """Mirrors DatasetDescriptor in api/client.ts, including the paths the
    frontend uses to fetch CSVs client-side in offline mode."""

    id: str
    label: str
    provenance: Provenance
    disclosure: str
    disease_path: str
    matrix_path: str
    #: Not in the TS interface (extra fields are ignored there); useful in /docs.
    available: bool = True


class DatasetRef(CamelModel):
    id: str
    label: str
    provenance: Provenance


class ScoredDrug(CamelModel):
    drug: str
    reversal_score: float


class Candidate(CamelModel):
    drug: str
    reversal_score: float
    rank: int
    known_for_disease: bool
    novelty_label: NoveltyLabel
    #: None when no structure table is loaded -- the screen is on standby, and
    #: score fusion uses filters.combine_scores()'s neutral 0.5 in its place.
    safety_score: float | None
    reversal_scaled: float
    novelty_bonus: float
    final_score: float
    final_rank: int


class RecoveryResult(CamelModel):
    disease: str
    top_k: int
    reference_set_size: int
    recovered_drugs: list[str]
    recovered_count: int
    recovery_rate: float
    novel_candidates: list[str]


class SyntheticCheck(CamelModel):
    recovered: list[str]
    recovered_count: int
    planted_total: int
    recovery_rate: float
    reinforcing_planted: list[str]
    reinforcing_ranks: list[Candidate]


class PipelineResult(CamelModel):
    settings: PipelineSettings
    dataset: DatasetRef
    method_label: str
    genes_matched: int
    drugs_scored: int
    all_scores: list[ScoredDrug]
    candidates: list[Candidate]
    recovery: RecoveryResult | None
    synthetic: SyntheticCheck | None
    #: Real wall-clock cost per stage id, in ms. Keys are STAGE_IDS.
    timings: dict[str, float]
    safety_active: bool
    disease_vec: list[float]
    disease_genes: list[str]

    # --- fields beyond the TS interface; ignored by the UI, read by humans ---
    #: True when a live run failed and this is the last known-good precomputed
    #: result. Never set on a fresh computation.
    stale: bool = False
    stale_reason: str | None = None
    #: True when this response came from the in-process result cache.
    cached: bool = False


class RunRequest(CamelModel):
    """POST /api/run body: {datasetId, settings} per the architecture plan.
    datasetId may be omitted, in which case settings.datasetId is used."""

    # A working example, so "Try it out -> Execute" in /docs runs the real
    # pipeline instead of failing on Swagger's "string" placeholder. The point
    # of shipping /docs is that someone can poke the API without reading this
    # file first.
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "datasetId": "synthetic-benchmark",
                    "settings": {
                        "datasetId": "synthetic-benchmark",
                        "diseaseName": "rheumatoid arthritis",
                        "method": "cosine-fast",
                        "displayTopN": 15,
                        "validationTopK": 20,
                        "weights": {"reversal": 0.6, "safety": 0.2, "novelty": 0.2},
                        "wtcsWeighted": True,
                    },
                }
            ]
        }
    )

    dataset_id: str | None = Field(default=None, examples=["synthetic-benchmark"])
    settings: PipelineSettings = Field(default_factory=PipelineSettings)


class GeneContribution(CamelModel):
    gene: str
    disease_log_fc: float = Field(alias="diseaseLogFC")
    drug_zscore: float
    contribution: float
    direction: Direction


class Pathway(CamelModel):
    term: str
    overlap: str
    adjusted_p_value: float
    genes: str


class ExplainResult(CamelModel):
    drug: str
    summary: str
    top_genes: list[GeneContribution]
    reversed_count: int
    #: None when enrichment was not run or could not run; `pathways_note`
    #: always says which, so the UI never shows a silent blank panel.
    pathways: list[Pathway] | None = None
    pathways_note: str | None = None


class ValidationResult(CamelModel):
    dataset: DatasetRef
    disease: str
    method_label: str
    top_k: int
    #: Real known-drug recovery. None when the library holds no real drug names.
    recovery: RecoveryResult | None
    #: Planted-signal check, used only on synthetic data. Never conflated above.
    synthetic: SyntheticCheck | None
    statement: str


class StageErrorBody(CamelModel):
    stage: str
    type: str
    message: str
    traceback: str | None = None


class ErrorResponse(CamelModel):
    error: StageErrorBody
