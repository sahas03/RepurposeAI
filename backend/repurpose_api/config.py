"""
config.py
Every path, origin and tuning knob the service needs, resolved once at import.

The service deliberately owns NO pipeline logic and NO copy of the data: it
points at the existing repurposeai/ package in this repo and reads the same
data/raw/*.csv the Streamlit dashboard reads. Nothing here is duplicated from
src/ -- see bridge.py for how the real functions are imported.
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/repurpose_api/config.py -> backend/ -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

PACKAGE_DIR = Path(os.environ.get("REPURPOSEAI_PACKAGE_DIR", REPO_ROOT / "repurposeai"))
SRC_DIR = PACKAGE_DIR / "src"
PIPELINE_APP_DIR = PACKAGE_DIR / "app"
DATA_DIR = Path(os.environ.get("REPURPOSEAI_DATA_DIR", PACKAGE_DIR / "data" / "raw"))

# Optional inputs. Absent is the normal case and is handled, never fatal:
# without a structure table the Lipinski screen stays on standby and
# filters.combine_scores() falls back to its neutral 0.5, exactly as the
# dashboard behaves today.
SMILES_LOOKUP_PATH = DATA_DIR / "smiles_lookup.csv"
APPROVED_DRUGS_PATH = DATA_DIR / "approved_drugs.txt"

PRECOMPUTE_DIR = Path(os.environ.get("REPURPOSEAI_PRECOMPUTE_DIR", BACKEND_ROOT / "precomputed"))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


#: Serve the last known-good precomputed result (flagged stale) when a live run
#: fails, instead of showing a crash during the demo. See scripts/precompute_demo.py.
STALE_FALLBACK_ENABLED = _flag("REPURPOSEAI_STALE_FALLBACK", True)

#: Include full tracebacks in error responses. Off by default so a failure in
#: front of judges is one clean sentence, not a wall of stack frames.
DEBUG = _flag("REPURPOSEAI_DEBUG", False)

#: Max (datasetId, settings) result entries held in memory.
CACHE_SIZE = _int("REPURPOSEAI_CACHE_SIZE", 32)

#: Seconds to wait on Enrichr before giving up (venue wifi is not a dependency).
ENRICHR_TIMEOUT = _int("REPURPOSEAI_ENRICHR_TIMEOUT", 6)

# Vite takes the next free port when its default is busy (5173 -> 5174 -> ...),
# and .claude/launch.json pins the frontend to 5199. A CORS allowlist that only
# covers 5173 therefore breaks the moment a stale dev server is still running,
# with a browser-console CORS error and a perfectly healthy-looking backend.
# Cover the range it actually uses.
_VITE_PORTS = (5173, 5174, 5175, 5176, 5199, 4173, 4174, 3000)
_DEFAULT_ORIGINS = [
    f"http://{host}:{port}" for port in _VITE_PORTS for host in ("localhost", "127.0.0.1")
]

_origins_env = os.environ.get("REPURPOSEAI_CORS_ORIGINS", "").strip()
#: "*" is accepted for a hostile-network demo where the origin is unknown.
CORS_ORIGINS = (
    [o.strip() for o in _origins_env.split(",") if o.strip()] if _origins_env else _DEFAULT_ORIGINS
)

API_TITLE = "RepurposeAI API"
API_VERSION = "1.0.0"
