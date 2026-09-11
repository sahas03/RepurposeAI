"""
test_pipeline.py
End-to-end smoke test: mock data -> data loading -> matching -> filtering ->
interpretability -> validation-style recovery check.

Run: python tests/test_pipeline.py
(Uses only the "planted" mock data, no internet or real data required.)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_mock_data
from data_loader import load_disease_signature, load_l1000_matrix, harmonize_genes, zscore_disease_signature
from signature_matching import cosine_reversal_score, rank_candidates
from interpretability import top_contributing_genes

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def main():
    print("=" * 60)
    print("STEP 0: generating mock data")
    print("=" * 60)
    generate_mock_data.main()

    print("\n" + "=" * 60)
    print("STEP 1: loading + harmonizing")
    print("=" * 60)
    disease_df = load_disease_signature(os.path.join(DATA_DIR, "disease_signature.csv"))
    l1000_df = load_l1000_matrix(os.path.join(DATA_DIR, "l1000_matrix.csv"))
    disease_df, l1000_df = harmonize_genes(disease_df, l1000_df)
    print(f"Shared genes after harmonization: {len(disease_df)}")
    assert len(disease_df) > 0, "No shared genes -- harmonization failed"

    print("\n" + "=" * 60)
    print("STEP 2: cosine reversal scoring")
    print("=" * 60)
    disease_vec = zscore_disease_signature(disease_df)
    scores = cosine_reversal_score(disease_vec, l1000_df)
    ranked = rank_candidates(scores, top_n=10)
    print(ranked.to_string(index=False))

    top_drugs = set(ranked["drug"].head(5))
    planted_reversal = {"planted_reversal_drug_0", "planted_reversal_drug_1", "planted_reversal_drug_2"}
    recovered = top_drugs & planted_reversal
    print(f"\nPlanted reversal drugs recovered in top 5: {recovered}")
    assert len(recovered) >= 2, (
        "Sanity check FAILED: fewer than 2 of the 3 planted reversal drugs "
        "were recovered in the top 5. Something is wrong with the scoring logic."
    )
    print("PASSED: matching engine correctly recovers planted signal.")

    print("\n" + "=" * 60)
    print("STEP 3: interpretability")
    print("=" * 60)
    best_drug = ranked.iloc[0]["drug"]
    genes_df = top_contributing_genes(disease_vec, l1000_df[best_drug], top_n=5)
    print(f"Top contributing genes for {best_drug}:")
    print(genes_df.to_string(index=False))

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED — pipeline is working end-to-end on mock data.")
    print("Next: swap in real disease_signature.csv and l1000_matrix.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
