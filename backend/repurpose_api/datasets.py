"""
datasets.py
Dataset registry + harmonised loading, cached on file identity.

The registry mirrors DATASETS in frontend/src/api/client.ts: same ids, same
labels, same disclosure text. The disclosure string is the one thing in this
service that must never drift or be softened -- it is what the UI shows a judge
verbatim to describe what the numbers actually are.

A second, optional entry ("real-lincs") is wired up but reports available=False
until Group 1 drops real CSVs into data/raw/. Nothing else has to change when
they land: the schema is already the one data_loader.py expects.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import bridge, config
from .schemas import DatasetDescriptor


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    label: str
    provenance: str
    disclosure: str
    disease_file: str
    matrix_file: str

    @property
    def disease_path(self) -> Path:
        return config.DATA_DIR / self.disease_file

    @property
    def matrix_path(self) -> Path:
        return config.DATA_DIR / self.matrix_file

    @property
    def available(self) -> bool:
        return self.disease_path.is_file() and self.matrix_path.is_file()

    def descriptor(self) -> DatasetDescriptor:
        return DatasetDescriptor(
            id=self.id,
            label=self.label,
            provenance=self.provenance,
            disclosure=self.disclosure,
            # Relative paths, matching what the frontend fetches from public/
            # when it runs the pipeline in-page as an offline fallback.
            disease_path=f"data/{self.disease_file}",
            matrix_path=f"data/{self.matrix_file}",
            available=self.available,
        )


REGISTRY: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        id="synthetic-benchmark",
        label="Synthetic Benchmark",
        provenance="synthetic",
        # Verbatim from frontend/src/api/client.ts -- do not reword.
        disclosure=(
            "Computer-generated benchmark from scripts/generate_mock_data.py. Gene symbols "
            "(GENE0000) and compound identifiers (drug_042) are placeholders, not real biology. "
            "Three compounds carry a deliberately planted reversal signal and two carry a "
            "reinforcing one, so the ranking can be checked against known ground truth. Every "
            "score shown is computed live from these files."
        ),
        disease_file="disease_signature.csv",
        matrix_file="l1000_matrix.csv",
    ),
    DatasetSpec(
        id="real-lincs",
        label="LINCS L1000 + GEO (real)",
        provenance="real",
        disclosure=(
            "Real disease signature derived from a GEO series (rheumatoid arthritis synovium vs. "
            "healthy control) matched against a LINCS L1000 Level 5 perturbation library. "
            "Provenance -- accession numbers, sample counts and preprocessing decisions -- is "
            "recorded alongside the CSVs by whoever prepared them."
        ),
        disease_file="disease_signature_real.csv",
        matrix_file="l1000_matrix_real.csv",
    ),
)

BY_ID = {spec.id: spec for spec in REGISTRY}


class DatasetNotFound(Exception):
    """Unknown dataset id, or a registered dataset whose CSVs are not present."""


@dataclass
class PreparedDataset:
    """A harmonised dataset, in exactly the form the pipeline stages consume."""

    spec: DatasetSpec
    disease_df: pd.DataFrame          # harmonised: gene, logFC, pvalue
    l1000_df: pd.DataFrame            # harmonised: genes x drugs
    disease_genes_before: int
    drugs_before: int
    #: Real wall-clock ms of the load/harmonise calls that produced this object.
    #: Zero-ish on a cache hit, which is the truth -- see README on timings.
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def genes(self) -> list[str]:
        return [str(g) for g in self.l1000_df.index]

    @property
    def drugs(self) -> list[str]:
        return [str(c) for c in self.l1000_df.columns]


def list_descriptors(include_unavailable: bool = False) -> list[DatasetDescriptor]:
    return [s.descriptor() for s in REGISTRY if include_unavailable or s.available]


def get_spec(dataset_id: str) -> DatasetSpec:
    spec = BY_ID.get(dataset_id)
    if spec is None:
        known = sorted(s.id for s in REGISTRY if s.available)
        raise DatasetNotFound(f"Unknown dataset {dataset_id!r}. Available: {known}")
    if not spec.available:
        missing = [str(p) for p in (spec.disease_path, spec.matrix_path) if not p.is_file()]
        raise DatasetNotFound(
            f"Dataset {dataset_id!r} is registered but its data files are not present yet: "
            + ", ".join(missing)
        )
    return spec


def _fingerprint(spec: DatasetSpec) -> tuple:
    """Identity of the files on disk, so edited CSVs invalidate the cache."""
    return tuple(
        (str(p), p.stat().st_mtime_ns, p.stat().st_size)
        for p in (spec.disease_path, spec.matrix_path)
    )


def fingerprint(dataset_id: str) -> tuple:
    """Public file-identity of a dataset, for building cache keys elsewhere."""
    return _fingerprint(get_spec(dataset_id))


_cache: dict[tuple, PreparedDataset] = {}


def prepare(dataset_id: str) -> PreparedDataset:
    """Load + harmonise a dataset, reusing the cached copy when files are unchanged.

    Each call into src/ goes through run_stage() so a failure names the stage
    that broke instead of surfacing a raw traceback.
    """
    spec = get_spec(dataset_id)
    key = (spec.id, _fingerprint(spec))
    hit = _cache.get(key)
    if hit is not None:
        # Real timings for a cache hit: the work genuinely did not happen again.
        return PreparedDataset(
            spec=hit.spec,
            disease_df=hit.disease_df,
            l1000_df=hit.l1000_df,
            disease_genes_before=hit.disease_genes_before,
            drugs_before=hit.drugs_before,
            timings={"disease": 0.0, "matrix": 0.0, "harmonize": 0.0},
        )

    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    disease_raw = bridge.run_stage(
        "load disease signature", bridge.load_disease_signature, str(spec.disease_path)
    )
    timings["disease"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    l1000_raw = bridge.run_stage(
        "load drug library", bridge.load_l1000_matrix, str(spec.matrix_path)
    )
    timings["matrix"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    disease_df, l1000_df = bridge.run_stage(
        "harmonize genes", bridge.harmonize_genes, disease_raw, l1000_raw
    )
    timings["harmonize"] = (time.perf_counter() - t0) * 1000

    prepared = PreparedDataset(
        spec=spec,
        disease_df=disease_df,
        l1000_df=l1000_df,
        disease_genes_before=len(disease_raw),
        drugs_before=l1000_raw.shape[1],
        timings=timings,
    )
    _cache[key] = prepared
    return prepared


# --------------------------------------------------------------------------
# Optional structure table for the Lipinski screen.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SafetyTable:
    smiles: dict[str, str]
    approved: set[str]


def load_safety_table() -> SafetyTable | None:
    """Read data/raw/smiles_lookup.csv (+ approved_drugs.txt) if present.

    Returns None when no structure table ships with the repo -- which is the
    current state, and why safetyActive is False and safetyScore is null.
    """
    if not config.SMILES_LOOKUP_PATH.is_file():
        return None
    if not bridge.RDKIT_AVAILABLE:
        return None

    df = pd.read_csv(config.SMILES_LOOKUP_PATH)
    cols = {c.lower(): c for c in df.columns}
    drug_col = cols.get("drug") or cols.get("name") or df.columns[0]
    smiles_col = cols.get("smiles") or df.columns[1]
    smiles = {
        str(r[drug_col]): str(r[smiles_col])
        for _, r in df.iterrows()
        if pd.notna(r[smiles_col])
    }

    approved: set[str] = set()
    if config.APPROVED_DRUGS_PATH.is_file():
        approved = {
            line.strip()
            for line in config.APPROVED_DRUGS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    return SafetyTable(smiles=smiles, approved=approved)
