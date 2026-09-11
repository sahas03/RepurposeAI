"""
build_indication_lookup.py
Builds the {drug_name: {indications}} lookup that src/filters.py's
apply_novelty_filter() takes as its `known_indications` argument.

SCOPE: every molecule ChEMBL records with the MeSH heading
"Arthritis, Rheumatoid", at any trial phase -- not just the 9 names that
used to be hard-coded in validate.py's _FALLBACK_SETS.

TWO THINGS THIS SCRIPT HAS TO GET RIGHT, both easy to get wrong:

 1. KEY CASE. apply_novelty_filter does `known_indications.get(d, set())`
    where d is the drug string straight out of l1000_matrix.csv's columns.
    That dict lookup is CASE-SENSITIVE (only the indication VALUES are
    compared case-insensitively). So for any compound that exists in the
    L1000 pool, the key must be the exact column spelling -- "S-ruxolitinib",
    not "s-ruxolitinib".

 2. INDICATION STRING. apply_novelty_filter tests
    `disease_name.lower() in {x.lower() for x in indications}` -- a literal
    equality test, with no MeSH awareness. Passing disease_name="rheumatoid
    arthritis" against ChEMBL's "Arthritis, Rheumatoid" matches NOTHING.
    The caller must pass the MeSH spelling. Both spellings are therefore
    written into every drug's indication set below, so the lookup works
    whichever string the caller uses.

Outputs data/raw/ra_indications.json and .csv.
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT/"data"/"raw", ROOT/"data"/"processed"
RA_MESH, RA_COLLOQUIAL = "Arthritis, Rheumatoid", "rheumatoid arthritis"

# --- L1000 column names, for exact-case keying -------------------------------
matrix = PROC/"l1000_matrix.csv"
if not matrix.exists():
    sys.exit(f"missing {matrix} -- real L1000 matrix required for name matching")
with matrix.open(encoding="utf-8") as f:
    pool = [c.strip() for c in f.readline().rstrip("\n").split(",")[1:]]
pool_ci = {c.lower(): c for c in pool}
print(f"L1000 pool: {len(pool)} compounds")

# --- ChEMBL RA molecules (all 318, superset of the pool) ---------------------
raw = json.loads((PROC/"ra_all_chembl_raw.json").read_text(encoding="utf-8"))
names = raw["names"]
print(f"ChEMBL molecules with '{RA_MESH}': {len(names)}")

# --- existing per-drug full indication sets for pool compounds ---------------
existing: dict[str, set[str]] = {}
ind_csv = PROC/"indications.csv"
if ind_csv.exists():
    with ind_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d, i = (row.get("drug") or "").strip(), (row.get("indication") or "").strip()
            if d and i:
                existing.setdefault(d, set()).add(i)
    print(f"reused indications.csv: {len(existing)} drugs with full indication sets")

lookup: dict[str, set[str]] = {}
prov: dict[str, str] = {}

def add(key: str, inds: set[str], source: str):
    lookup.setdefault(key, set()).update(inds)
    lookup[key].update({RA_MESH, RA_COLLOQUIAL})   # see note 2 in the docstring
    prov.setdefault(key, source)

# 1) every ChEMBL RA molecule, keyed to the pool spelling where one exists
for cid, rec in names.items():
    cands = [rec["pref_name"]] + rec["synonyms"]
    key = None
    for c in cands:
        if c and c.lower() in pool_ci:
            key = pool_ci[c.lower()]; break
    if key is None:                       # not in the pool: key on lowercase pref_name
        key = (rec["pref_name"] or cid).lower()
    add(key, existing.get(key, set()), "chembl_ra" + ("" if key in pool else "_not_in_pool"))

# 2) anything already flagged RA in indications.csv but missed above
for d, inds in existing.items():
    if RA_MESH in inds and d not in lookup:
        add(d, inds, "indications_csv")

in_pool = sorted(k for k in lookup if k in pool)
out_pool = sorted(k for k in lookup if k not in pool)
print(f"\nRA-indicated drugs in lookup: {len(lookup)}  (in L1000 pool: {len(in_pool)}, outside: {len(out_pool)})")

RAW.mkdir(parents=True, exist_ok=True)
(RAW/"ra_indications.json").write_text(
    json.dumps({k: sorted(v) for k, v in sorted(lookup.items())}, indent=1), encoding="utf-8")
with (RAW/"ra_indications.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["drug","indication","in_l1000_pool","source"])
    for k in sorted(lookup):
        for i in sorted(lookup[k]):
            w.writerow([k, i, k in pool, prov[k]])
print(f"wrote {RAW/'ra_indications.json'} and .csv")
json.dump(in_pool, open(RAW/"ra_in_pool.json","w"), indent=1)

CHECK = ["methotrexate","baricitinib","tofacitinib","upadacitinib","etanercept",
         "adalimumab","infliximab","tocilizumab","sarilumab",
         "sulfasalazine","leflunomide","hydroxychloroquine"]
print("\n=== CROSS-CHECK (12 required drugs) ===")
miss=[]
for d in CHECK:
    k = pool_ci.get(d, d)
    hit = k in lookup or d in lookup
    key = k if k in lookup else (d if d in lookup else None)
    print(f"  {d:20s} {'PRESENT' if hit else 'MISSING':8s} key={key!r:24s} in_pool={d in pool_ci}")
    if not hit: miss.append(d)
print(("ALL 12 PRESENT" if not miss else f"MISSING: {miss}"))
