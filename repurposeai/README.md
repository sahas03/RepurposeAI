# RepurposeAI — Starter Codebase

CBIT National Level Ideathon 5.0 — Life Sciences & AI | Target disease: **Rheumatoid Arthritis**

This is a working starting point, not a finished product — every core module has
been run and verified end-to-end on synthetic data (see "Verify it works" below).
Your job over the next few days is to swap in real data and extend the modules,
not to build from scratch.

## Day 1 — Do this tonight (Tue 8 Sept)

### 1. Set up the environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Verify it works (no internet, no real data needed)
```bash
python tests/test_pipeline.py
```
This generates synthetic "planted" data and confirms the matching engine and
interpretability layer correctly recover the planted reversal signal. If this
passes, your environment and core logic are both solid — everyone on the team
should run this tonight and confirm it passes on their own machine.

### 3. Try the demo dashboard on mock data
```bash
streamlit run app/dashboard.py
```
Leave "Use mock/demo data" checked and click **Run pipeline** — you should see
a ranked candidate table and a gene-level explanation panel. This is your Day 4
demo shell, already working today.

### 4. Start real data downloads in parallel (these take time — start now)
- **LINCS L1000**: register at clue.io, download a Level 5 GCTX file
  (GSE92742 or GSE70138) plus `gene_info` and `sig_info` metadata files.
- **Disease signature**: find a GEO series comparing RA synovial tissue vs.
  healthy controls (search GEO for "rheumatoid arthritis synovium expression").
  Note the accession number and which GSM samples are disease vs. healthy.
- **DrugBank / ChEMBL**: download the open-data structures export (for SMILES,
  used by `src/filters.py`) and indication data (for `src/filters.py` novelty
  checks).

See `scripts/prepare_real_data.py` for a starter script to convert these
downloads into the CSV formats the pipeline expects — **run that script on
your own machine**, since it needs normal internet access to GEO/clue.io.

## Project layout

```
repurposeai/
├── requirements.txt
├── data/
│   └── raw/                    # disease_signature.csv, l1000_matrix.csv go here
├── src/
│   ├── data_loader.py          # load + harmonize disease & drug signatures
│   ├── signature_matching.py   # cosine similarity + WTCS reversal scoring
│   ├── filters.py              # safety (Lipinski) + novelty filtering
│   ├── interpretability.py     # gene-level rationale + pathway enrichment
│   └── validate.py             # retrospective validation against known drugs
├── scripts/
│   ├── generate_mock_data.py   # synthetic data for testing (run anytime)
│   └── prepare_real_data.py    # GEO + L1000 -> CSV conversion (run locally)
├── app/
│   └── dashboard.py            # Streamlit demo
└── tests/
    └── test_pipeline.py        # end-to-end smoke test
```

## Day-by-day (see full sprint plan PDF for detail)

| Day | Focus |
|---|---|
| Tue (today) | Environment + mock data working (done if `test_pipeline.py` passes) |
| Wed | Real data loaded, `cosine_reversal_score` running on real RA signature |
| Thu | Safety/novelty filtering (`filters.py`) + gene rationale + pathway enrichment |
| Fri | Validation against known RA drugs (`validate.py`), dashboard polish, pitch rehearsal |

## Known reference drugs for validation (already in `validate.py`)

JAK inhibitors (baricitinib, tofacitinib, upadacitinib), anti-TNF biologics
(etanercept, adalimumab, infliximab), anti-IL6 (tocilizumab, sarilumab), and
methotrexate. If your top-20 ranked candidates recover several of these from a
blind run on the real RA signature, that is your strongest validation result —
lead with it in the pitch.

## If you fall behind (fallback order — see sprint plan for detail)

1. Drop the optional autoencoder embedding (WTCS/cosine alone is credible).
2. Drop live ADMET prediction — use static DrugBank flags only.
3. Drop dashboard polish — a narrated notebook can substitute for a UI.
4. **Never drop**: the validation check (`validate.py`) and gene-level
   explanations (`interpretability.py`) — these are what make this a science
   project instead of a lookup table.
