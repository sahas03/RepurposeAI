"""Small serialization helpers shared by services and websocket handlers."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def jsonable(value: Any) -> Any:
    """Recursively convert a value into JSON-safe primitives (for WS payloads, Celery results)."""
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if hasattr(value, "item"):  # numpy scalar
        return jsonable(value.item())
    if hasattr(value, "tolist"):  # numpy array
        return jsonable(value.tolist())
    return str(value)
