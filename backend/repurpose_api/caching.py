"""
caching.py
In-process memoisation of (dataset, settings) -> PipelineResult.

Repeat runs of the same settings return instantly, which makes it possible to
pre-warm the exact configuration you plan to demo. The cache key includes the
dataset files' identity (path, mtime, size), so regenerating or swapping a CSV
invalidates it automatically -- a stale result is never served as a live one.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

from . import config, datasets
from .schemas import PipelineResult, PipelineSettings


def _optional_inputs() -> list[list[str]]:
    """Identity of the optional structure table, which changes what a run produces.

    Without this in the key, dropping smiles_lookup.csv into data/raw/ on a
    running server would keep serving cached results computed while the Lipinski
    screen was still on standby.
    """
    out = []
    for path in (config.SMILES_LOOKUP_PATH, config.APPROVED_DRUGS_PATH):
        if path.is_file():
            st = path.stat()
            out.append([str(path), str(st.st_mtime_ns), str(st.st_size)])
        else:
            out.append([str(path), "absent", "absent"])
    return out


def result_key(settings: PipelineSettings) -> str:
    """Stable hash of the settings plus every input file the run depends on."""
    payload = {
        "settings": settings.model_dump(by_alias=True, mode="json"),
        "files": [list(map(str, entry)) for entry in datasets.fingerprint(settings.dataset_id)],
        "optional": _optional_inputs(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def settings_digest(settings: PipelineSettings) -> str:
    """Hash of the settings alone, ignoring data files.

    Used to name precomputed results on disk, which must stay findable after a
    restart even though mtimes may have changed.
    """
    blob = json.dumps(
        settings.model_dump(by_alias=True, mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


_store: OrderedDict[str, PipelineResult] = OrderedDict()


def get(key: str) -> PipelineResult | None:
    hit = _store.get(key)
    if hit is None:
        return None
    _store.move_to_end(key)
    # Copy so the caller's `cached` flag never mutates the stored entry.
    return hit.model_copy(update={"cached": True})


def put(key: str, result: PipelineResult) -> None:
    _store[key] = result
    _store.move_to_end(key)
    while len(_store) > config.CACHE_SIZE:
        _store.popitem(last=False)


def clear() -> None:
    _store.clear()


def stats() -> dict[str, int]:
    return {"entries": len(_store), "maxEntries": config.CACHE_SIZE}
