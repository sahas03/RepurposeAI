"""
generate_mock_data_large.py
Larger, more realistic synthetic data for stress-testing the scoring engine at
LINCS L1000 scale (~1,000 shared genes x 500-1,000 drugs), before real data lands.

Differences from generate_mock_data.py (which is left untouched):
  - Scale: default 1,000 genes x 800 drugs (vs 200 x 150).
  - Realistic disease signature: most genes are NULL (logFC ~ N(0, 0.3)); only a
    subset are DEGs (default 100 up + 100 down). Real RA-vs-healthy data
    intersected with L1000 looks like this -- not "every gene is +/-2".
    The null genes also get a small non-zero mean shift, because real logFC
    distributions are rarely centered exactly at 0.
  - Planted drugs at graded strengths, so we can see WHERE recovery breaks down
    instead of only testing a trivially clean signal. Planted drugs reverse
    (or reinforce) only the DEG subset, with realistic noise elsewhere.
  - Writes to an explicit output directory. It NEVER defaults to data/raw/,
    so it can't clobber the shared real-data files.
  - Uses a local RNG (np.random.default_rng), so importing it doesn't
    reseed numpy's global state.

Naming convention kept compatible with tests/test_pipeline.py and
app/validation_helpers.py: "planted_reversal_drug_<i>" / "planted_reinforcing_drug_<i>".

Usage:
    python scripts/generate_mock_data_large.py --out-dir data/processed/mock_large
    python scripts/generate_mock_data_large.py --out-dir /tmp/x --n-genes 978 --n-drugs 1000
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

N_GENES = 1000
N_DRUGS = 800
N_UP = 100
N_DOWN = 100
SEED = 7

# (strength, noise_sd) per planted drug. strength scales the mirrored DEG signal;
# noise_sd is the drug-level noise on ALL genes (real L1000 z-scores are noisy).
PLANTED_REVERSAL = [(1.0, 0.5), (1.0, 0.5), (1.0, 0.5), (0.6, 1.0), (0.4, 1.0), (0.25, 1.0)]
PLANTED_REINFORCING = [(1.0, 0.5), (1.0, 0.5)]


def make_data(out_dir: str, n_genes: int = N_GENES, n_drugs: int = N_DRUGS,
              n_up: int = N_UP, n_down: int = N_DOWN, seed: int = SEED) -> dict:
    """Generate the synthetic set, write both CSVs to out_dir, return metadata."""
    if n_up + n_down > n_genes:
        raise ValueError("n_up + n_down must be <= n_genes")
    n_planted = len(PLANTED_REVERSAL) + len(PLANTED_REINFORCING)
    if n_planted > n_drugs:
        raise ValueError(f"n_drugs must be >= {n_planted} (number of planted drugs)")

    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    # Placeholder IDs -- deliberately a DIFFERENT format from the original generator
    # (and shuffled) so nothing downstream can silently depend on "GENE0000"-style
    # names or on genes arriving in index order.
    genes = np.array([f"MOCK_G{i}" for i in range(n_genes)])
    rng.shuffle(genes)

    # --- Disease signature: sparse DEGs on top of a mostly-null background ---
    logFC = rng.normal(0.15, 0.3, n_genes)  # null genes, slightly off-center
    deg_idx = rng.choice(n_genes, n_up + n_down, replace=False)
    up_idx, down_idx = deg_idx[:n_up], deg_idx[n_up:]
    logFC[up_idx] = rng.normal(1.8, 0.5, n_up)
    logFC[down_idx] = rng.normal(-1.8, 0.5, n_down)

    is_deg = np.zeros(n_genes, dtype=bool)
    is_deg[deg_idx] = True
    pvalue = np.where(is_deg, rng.uniform(1e-6, 0.01, n_genes), rng.uniform(0.01, 1.0, n_genes))

    disease_df = pd.DataFrame({"gene": genes, "logFC": logFC, "pvalue": pvalue})

    # --- Drug matrix: background noise, like L1000 level-5 moderated z-scores ---
    drug_names = [f"drug_{i:04d}" for i in range(n_drugs)]
    matrix = rng.normal(0, 1, size=(n_genes, n_drugs))

    # Planted drugs act on the DEG subset only (the rest stays as noise)
    deg_signal = np.where(is_deg, logFC, 0.0)

    col = 0
    reversal_names, reinforcing_names = [], []
    for strength, noise in PLANTED_REVERSAL:
        matrix[:, col] = -strength * deg_signal + rng.normal(0, noise, n_genes)
        drug_names[col] = f"planted_reversal_drug_{col}"
        reversal_names.append(drug_names[col])
        col += 1
    for strength, noise in PLANTED_REINFORCING:
        matrix[:, col] = strength * deg_signal + rng.normal(0, noise, n_genes)
        drug_names[col] = f"planted_reinforcing_drug_{col}"
        reinforcing_names.append(drug_names[col])
        col += 1

    # Shuffle drug column order too, so planted drugs aren't always columns 0..7
    perm = rng.permutation(n_drugs)
    l1000_df = pd.DataFrame(matrix[:, perm], index=genes, columns=[drug_names[i] for i in perm])
    l1000_df.index.name = "gene"

    disease_path = os.path.join(out_dir, "disease_signature.csv")
    l1000_path = os.path.join(out_dir, "l1000_matrix.csv")
    disease_df.to_csv(disease_path, index=False)
    l1000_df.to_csv(l1000_path)

    return {
        "disease_path": disease_path,
        "l1000_path": l1000_path,
        "n_genes": n_genes,
        "n_drugs": n_drugs,
        "planted_reversal": reversal_names,
        "planted_reversal_strengths": dict(zip(reversal_names, PLANTED_REVERSAL)),
        "planted_reinforcing": reinforcing_names,
        "deg_genes": sorted(genes[deg_idx].tolist()),
    }


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--out-dir", required=True,
                   help="Where to write the CSVs (required on purpose -- never defaults to data/raw/).")
    p.add_argument("--n-genes", type=int, default=N_GENES)
    p.add_argument("--n-drugs", type=int, default=N_DRUGS)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args(argv)

    meta = make_data(args.out_dir, n_genes=args.n_genes, n_drugs=args.n_drugs, seed=args.seed)
    print(f"Wrote {meta['n_genes']}-gene disease signature and "
          f"{meta['n_genes']}x{meta['n_drugs']} drug matrix to {args.out_dir}")
    print("Planted reversal drugs (strength, noise_sd) -- should rank near the TOP:")
    for name, (s, n) in meta["planted_reversal_strengths"].items():
        print(f"  {name}: strength={s}, noise_sd={n}")
    print(f"Planted reinforcing drugs (should rank at the BOTTOM): {meta['planted_reinforcing']}")
    return meta


if __name__ == "__main__":
    main()
