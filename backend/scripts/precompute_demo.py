"""
precompute_demo.py
Run the settings you plan to demo and store the result as a known-good fallback.

Insurance, not a substitute for the live run: /api/run always tries to compute
fresh first. Only if that fails does it serve the stored result, flagged
`stale: true` with a reason, so a failure at the venue degrades to a visible
"this is a replay" instead of a crash in front of judges.

Run it after the data is final and before you present:

    cd backend
    python scripts/precompute_demo.py                    # frontend defaults
    python scripts/precompute_demo.py --all-methods      # every scoring method
    python scripts/precompute_demo.py --list             # what is already stored

Files land in backend/precomputed/ (override with REPURPOSEAI_PRECOMPUTE_DIR).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repurpose_api import config, precompute, service  # noqa: E402
from repurpose_api.schemas import PipelineSettings, Weights  # noqa: E402

METHODS = ("cosine", "cosine-fast", "wtcs")


def build_settings(args: argparse.Namespace, method: str) -> PipelineSettings:
    return PipelineSettings(
        dataset_id=args.dataset,
        disease_name=args.disease,
        method=method,
        display_top_n=args.display_top_n,
        validation_top_k=args.validation_top_k,
        weights=Weights(
            reversal=args.weight_reversal,
            safety=args.weight_safety,
            novelty=args.weight_novelty,
        ),
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="synthetic-benchmark")
    p.add_argument("--disease", default="rheumatoid arthritis")
    p.add_argument("--method", default="cosine-fast", choices=METHODS)
    p.add_argument("--all-methods", action="store_true", help="Precompute every scoring method.")
    p.add_argument("--display-top-n", type=int, default=15)
    p.add_argument("--validation-top-k", type=int, default=20)
    p.add_argument("--weight-reversal", type=float, default=0.6)
    p.add_argument("--weight-safety", type=float, default=0.2)
    p.add_argument("--weight-novelty", type=float, default=0.2)
    p.add_argument("--list", action="store_true", help="List stored results and exit.")
    args = p.parse_args()

    if args.list:
        stored = precompute.available()
        print(f"Precompute store: {config.PRECOMPUTE_DIR}")
        if not stored:
            print("  (empty -- run this script without --list to populate it)")
        for name in stored:
            print(f"  {name}")
        return 0

    methods = list(METHODS) if args.all_methods else [args.method]
    failures = 0

    for method in methods:
        settings = build_settings(args, method)
        label = f"{settings.dataset_id} / {method}"
        started = time.perf_counter()
        try:
            result = service.warm(settings)
        except Exception as e:  # noqa: BLE001 - report and continue to the next method
            failures += 1
            print(f"FAILED  {label}: {type(e).__name__}: {e}")
            continue

        path = precompute.save(result)
        elapsed = (time.perf_counter() - started) * 1000
        check = result.recovery or result.synthetic
        recovered = (
            f"{check.recovered_count} recovered"
            if check is not None
            else "no reference signal"
        )
        print(
            f"OK      {label}: {result.drugs_scored} compounds, {result.genes_matched} genes, "
            f"{recovered}, {elapsed:.0f} ms -> {path.name}"
        )

    if failures:
        print(f"\n{failures} of {len(methods)} runs failed. The store was not updated for those.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
