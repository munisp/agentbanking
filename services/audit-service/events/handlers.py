from schemas import AuditEventSchema
from services import AuditService
from database import get_session

def audit_received_handler(payload: AuditEventSchema):
    session = next(get_session())
    try:
        audit_service = AuditService(session)
        audit_service.create_audit(payload)
    finally:
        session.close()