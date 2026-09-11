"""Write-only audit trail helper, called from every state-changing service."""
import uuid

from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: uuid.UUID | None,
    action: AuditAction | str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    action_value = action.value if isinstance(action, AuditAction) else action
    entry = AuditLog(
        user_id=user_id,
        action=action_value,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        extra_metadata=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry
