import hashlib
import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session
from app.models.entities import AuditLog

logger = logging.getLogger("qpi.audit")


class AuditService:
    @staticmethod
    def hash_ip(ip_address: str) -> str:
        return hashlib.sha256(ip_address.encode('utf-8')).hexdigest()

    @classmethod
    def log_event(
        cls,
        db: Session,
        action: str,
        resource_id: UUID,
        actor_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1"
    ) -> AuditLog:
        ip_hash = cls.hash_ip(ip_address)
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            resource_id=resource_id,
            details=details or {},
            ip_hash=ip_hash
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(f"AUDIT LOG: Action='{action}' Resource='{resource_id}' Actor='{actor_id}'")
        return entry

    @classmethod
    def log_request(
        cls,
        db: Session,
        request: Request,
        action: str,
        resource_id: UUID,
        actor_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        ip = request.client.host if request.client else "unknown"
        return cls.log_event(db, action, resource_id, actor_id=actor_id, details=details, ip_address=ip)

    @classmethod
    def record_admin(
        cls,
        db: Session,
        request: Request,
        admin_id: Optional[UUID],
        action: str,
        entity_type: str,
        entity_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Stage an admin-panel audit entry in the caller's transaction (committed with the change itself)."""
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent")
        entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            resource_id=entity_id,
            details=details or {},
            ip_hash=cls.hash_ip(ip),
            user_agent=ua[:255] if ua else None,
        )
        db.add(entry)
        logger.info("ADMIN AUDIT: action=%s entity=%s:%s admin=%s", action, entity_type, entity_id, admin_id)
        return entry
