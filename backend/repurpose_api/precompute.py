"""
precompute.py
Last-known-good results on disk, for demo safety.

scripts/precompute_demo.py runs the settings you plan to present and stores the
result here. If a live call then fails at the venue, /api/run serves the stored
result with `stale: true` and a `staleReason` naming what went wrong, instead of
showing a crash. The flag is part of the payload, so the UI (and anyone reading
the JSON) can always tell a replayed result from a live one -- the fallback
never silently pretends to be a fresh computation.

Disable with REPURPOSEAI_STALE_FALLBACK=0.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import caching, config
from .schemas import PipelineResult, PipelineSettings

LATEST_NAME = "latest.json"


def _dir() -> Path:
    return config.PRECOMPUTE_DIR


def path_for(settings: PipelineSettings) -> Path:
    return _dir() / f"{settings.dataset_id}-{caching.settings_digest(settings)}.json"


def save(result: PipelineResult) -> Path:
    """Write a result to the store, and mark it as the newest known-good one."""
    _dir().mkdir(parents=True, exist_ok=True)
    # Stored results are, by definition, replayed later -- never persist a
    # `cached`/`stale` flag from the run that produced them.
    clean = result.model_copy(update={"cached": False, "stale": False, "stale_reason": None})
    blob = clean.model_dump_json(by_alias=True, indent=2)

    target = path_for(result.settings)
    target.write_text(blob, encoding="utf-8")
    (_dir() / LATEST_NAME).write_text(blob, encoding="utf-8")
    return target


def _read(path: Path) -> PipelineResult | None:
    if not path.is_file():
        return None
    try:
        return PipelineResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        # A corrupt fallback file must never take down the endpoint it exists
        # to protect; treat it as absent.
        return None


def load(settings: PipelineSettings) -> PipelineResult | None:
    """Best match for these settings: the exact file, else the newest stored result."""
    return _read(path_for(settings)) or _read(_dir() / LATEST_NAME)


def fallback(settings: PipelineSettings, reason: str) -> PipelineResult | None:
    """A stored result flagged as stale, or None when the store is empty."""
    if not config.STALE_FALLBACK_ENABLED:
        return None
    stored = load(settings)
    if stored is None:
        return None
    return stored.model_copy(update={"stale": True, "stale_reason": reason, "cached": False})


def available() -> list[str]:
    if not _dir().is_dir():
        return []
    return sorted(p.name for p in _dir().glob("*.json"))
