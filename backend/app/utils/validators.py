"""Reusable request/file validation helpers."""
import uuid

from app.core.config import settings
from app.core.exceptions import FileProcessingError, ValidationAppError


def validate_uuid(value: str, field_name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationAppError(f"'{field_name}' is not a valid UUID", {"value": str(value)}) from exc


def validate_upload_file(filename: str, size: int) -> str:
    if "." not in filename:
        raise FileProcessingError("Uploaded file has no extension", code="MISSING_EXTENSION")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_upload_extensions_list:
        raise FileProcessingError(
            f"File extension '.{ext}' is not supported",
            {"allowed": settings.allowed_upload_extensions_list},
            code="UNSUPPORTED_FILE_TYPE",
        )
    if size <= 0:
        raise FileProcessingError("Uploaded file is empty", code="EMPTY_FILE")
    if size > settings.MAX_UPLOAD_SIZE:
        raise FileProcessingError(
            f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE} bytes",
            {"max_size": settings.MAX_UPLOAD_SIZE, "actual_size": size},
            code="FILE_TOO_LARGE",
        )
    return ext


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
