"""
test_pipeline_real.py  --  REAL-DATA end-to-end smoke test.

NOT to be confused with test_pipeline.py, which is the SYNTHETIC test.
The difference matters, so it is spelled out here:

  tests/test_pipeline.py       reads data/raw/, and REGENERATES that directory
                               via generate_mock_data.main() on every run.
                               Asserts the planted reversal signals are
                               recovered. Requires no real data, no network.

  tests/test_pipeline_real.py  (this file) reads data/processed/, generates
                               nothing, and writes nothing. Asserts the real
                               data loads, harmonises and scores correctly.

WHAT THIS TEST DELIBERATELY DOES NOT ASSERT
-------------------------------------------
It does not assert that known RA drugs are recovered near the top of the
ranking, because on this dataset they are not, and that is an established
finding rather than a bug. Across cosine and WTCS, compound-mean /
best-of-N / dose-matched aggregation, and 26 per-cell-line tests, no
configuration beat its permutation null; baricitinib and tofacitinib rank
around 1500/1768 with positive (reinforcing) cosine. Adding a recovery
assertion here would encode a failure the pipeline cannot satisfy and would
send the next person hunting for a bug in correct code.

What it therefore checks is that the machinery is sound: the real files
parse, gene identifiers harmonise, scoring produces finite values across
the full compound pool, and interpretability resolves real gene symbols.

Run: python tests/test_pipeline_real.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data_loader import (  # noqa: E402
    harmonize_genes,
    load_disease_signature,
    load_l1000_matrix,
    zscore_disease_signature,
)
from interpretability import top_contributing_genes  # noqa: E402
from signature_matching import cosine_reversal_score, rank_candidates  # noqa: E402

# Real data only. Never data/raw/ -- see data/raw/README.md.
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

EXPECTED_SHARED_GENES = 952  # GSE55457 x L1000 landmark intersection


def main():
    print("=" * 64)
    print("STEP 1: loading + harmonising REAL data from data/processed/")
    print("=" * 64)
    disease_path = os.path.join(DATA_DIR, "disease_signature.csv")
    l1000_path = os.path.join(DATA_DIR, "l1000_matrix.csv")
    for p in (disease_path, l1000_path):
        assert os.path.exists(p), f"missing real data file: {p}"

    disease_df = load_disease_signature(disease_path)
    l1000_df = load_l1000_matrix(l1000_path)
    print(f"disease signature: {disease_df.shape[0]} genes")
    print(f"L1000 matrix:      {l1000_df.shape[0]} genes x {l1000_df.shape[1]} drugs")

    # Guard against data/raw/ mock data being pointed here by mistake.
    assert not str(disease_df["gene"].iloc[0]).startswith("GENE"), (
        "disease signature uses GENE#### placeholders -- this is SYNTHETIC mock "
        "data, not real data. Check DATA_DIR."
    )
    assert not any(str(c).startswith("planted_") for c in l1000_df.columns), (
        "L1000 matrix contains planted_* columns -- this is SYNTHETIC mock data."
    )

    disease_df, l1000_df = harmonize_genes(disease_df, l1000_df)
    shared = len(disease_df)
    print(f"Shared genes after harmonisation: {shared}")
    assert shared == EXPECTED_SHARED_GENES, (
        f"expected {EXPECTED_SHARED_GENES} shared genes, got {shared} -- the data "
        "files may have been regenerated or replaced with a different version"
    )

    print("\n" + "=" * 64)
    print("STEP 2: cosine reversal scoring")
    print("=" * 64)
    disease_vec = zscore_disease_signature(disease_df)
    scores = cosine_reversal_score(disease_vec, l1000_df)
    assert len(scores) == l1000_df.shape[1], "not every compound was scored"
    assert np.isfinite(scores.values).all(), "non-finite reversal scores produced"
    print(f"scored {len(scores)} compounds; range "
          f"[{scores.min():.4f}, {scores.max():.4f}]")
    print(rank_candidates(scores, top_n=10).to_string(index=False))

    # Presence check only -- deliberately NOT a rank/recovery assertion.
    for drug in ("baricitinib", "tofacitinib"):
        assert drug in l1000_df.columns, f"{drug} missing from the compound pool"
    print("\nvalidation drugs present in pool: baricitinib, tofacitinib "
          "(rank not asserted -- see module docstring)")

    print("\n" + "=" * 64)
    print("STEP 3: interpretability on real gene symbols")
    print("=" * 64)
    best = scores.index[0]
    genes_df = top_contributing_genes(disease_vec, l1000_df[best], top_n=5)
    print(f"Top contributing genes for {best}:")
    print(genes_df.to_string(index=False))
    assert not genes_df["gene"].astype(str).str.startswith("GENE0").any(), (
        "interpretability returned placeholder gene IDs"
    )

    print("\n" + "=" * 64)
    print("ALL CHECKS PASSED -- pipeline runs end-to-end on REAL data.")
    print("=" * 64)


if __name__ == "__main__":
    main()
