"""
generate_mock_data.py
Run this FIRST, today, before real data has finished downloading.

Generates a small synthetic disease signature + synthetic L1000-style drug
matrix, with a few "planted" drugs that are designed to score as strong
reversal candidates -- so you can verify the whole pipeline (Day 2-4 modules)
runs end-to-end correctly before real data is ready. This directly matches
Day 1's "dry run on a tiny subset" checkpoint.

Usage:
    python scripts/generate_mock_data.py
Produces:
    data/raw/disease_signature.csv
    data/raw/l1000_matrix.csv
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)

N_GENES = 200
N_DRUGS = 150
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    genes = [f"GENE{i:04d}" for i in range(N_GENES)]

    # --- Disease signature: half up-regulated, half down-regulated ---
    logFC = np.concatenate([
        np.random.normal(2.0, 0.5, N_GENES // 2),   # up-regulated in disease
        np.random.normal(-2.0, 0.5, N_GENES // 2),  # down-regulated in disease
    ])
    np.random.shuffle(logFC)
    pvalue = np.random.uniform(0.0001, 0.05, N_GENES)

    disease_df = pd.DataFrame({"gene": genes, "logFC": logFC, "pvalue": pvalue})
    disease_df.to_csv(os.path.join(OUT_DIR, "disease_signature.csv"), index=False)

    # --- Drug matrix: mostly random noise ---
    drug_names = [f"drug_{i:03d}" for i in range(N_DRUGS)]
    matrix = np.random.normal(0, 1, size=(N_GENES, N_DRUGS))

    # Plant 3 "true reversal" drugs: signature ~ -1 * disease signature + noise
    reversal_drug_idx = [0, 1, 2]
    for idx in reversal_drug_idx:
        matrix[:, idx] = -logFC + np.random.normal(0, 0.3, N_GENES)
        drug_names[idx] = f"planted_reversal_drug_{idx}"

    # Plant 2 "reinforcing" drugs (should score poorly): same direction as disease
    reinforce_idx = [3, 4]
    for idx in reinforce_idx:
        matrix[:, idx] = logFC + np.random.normal(0, 0.3, N_GENES)
        drug_names[idx] = f"planted_reinforcing_drug_{idx}"

    l1000_df = pd.DataFrame(matrix, index=genes, columns=drug_names)
    l1000_df.index.name = "gene"
    l1000_df.to_csv(os.path.join(OUT_DIR, "l1000_matrix.csv"))

    print(f"Wrote {len(disease_df)}-gene disease signature and "
          f"{l1000_df.shape[0]}x{l1000_df.shape[1]} drug matrix to {OUT_DIR}")
    print("Planted reversal drugs (should rank at the TOP): "
          f"{[drug_names[i] for i in reversal_drug_idx]}")
    print("Planted reinforcing drugs (should rank at the BOTTOM): "
          f"{[drug_names[i] for i in reinforce_idx]}")


if __name__ == "__main__":
    main()
