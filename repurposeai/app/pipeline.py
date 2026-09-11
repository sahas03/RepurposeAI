"""
pipeline.py
Thin, defensive wrapper around calls into src/*.py so a single misbehaving
stage (e.g. a teammate's overnight signature change in filters.py) surfaces
in the dashboard as one clear sentence naming the stage, never a raw
traceback in front of judges.

This file owns NO pipeline logic itself -- every call in dashboard.py that
touches src/ goes through run_stage() below with the exact current function
signature. If a teammate changes a function's arguments overnight, the
call site in dashboard.py is the one place to fix -- this wrapper doesn't
need to change.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable


class StageError(Exception):
    """Raised by run_stage() when a wrapped pipeline call fails.

    Carries the human-readable stage name plus the original exception, so
    the UI can show one clean sentence while the full traceback stays
    available in a collapsed "technical details" expander for whoever is
    driving the demo.
    """

    def __init__(self, stage: str, original: Exception):
        self.stage = stage
        self.original = original
        self.traceback_str = "".join(
            traceback.format_exception(type(original), original, original.__traceback__)
        )
        super().__init__(f"[{stage}] {type(original).__name__}: {original}")


def run_stage(stage: str, fn: Callable, *args, **kwargs) -> Any:
    """Call fn(*args, **kwargs); wrap any failure as a StageError tagged with `stage`."""
    try:
        return fn(*args, **kwargs)
    except StageError:
        raise
    except Exception as e:  # noqa: BLE001 - intentionally broad, this is the safety net
        raise StageError(stage, e) from e
