import uuid
from typing import Any

from sqlalchemy.orm import Session

from trustvault.db.models import AuditEvent


class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        event_type: str,
        *,
        status: str = "success",
        user_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            status=status,
            user_id=user_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata_json=metadata or {},
            **kwargs,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
