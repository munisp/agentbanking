import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from database import get_session
from models import User
from models.feedback import Feedback
from schemas.feedback import CreateFeedbackSchema, RespondToFeedbackSchema
from schemas import Context
from utils import create_logger, FeedbackStatus, FeedbackCategory

logger = create_logger(__name__)

feedback_router = APIRouter()


@feedback_router.get("")
def list_feedback(
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """List all feedback for the tenant. Optionally filter by status or category."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    query = db.query(Feedback).filter(Feedback.tenant_id == context.tenant_id)

    if status:
        try:
            status_enum = FeedbackStatus(status)
            query = query.filter(Feedback.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status value: {status}"
            )

    if category:
        try:
            category_enum = FeedbackCategory(category)
            query = query.filter(Feedback.category == category_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid category value: {category}"
            )

    feedbacks = query.order_by(Feedback.created_at.desc()).all()

    return JSONResponse(
        content={
            "message": "success",
            "feedbacks": [f.to_dict() for f in feedbacks],
            "total": len(feedbacks),
        },
        status_code=200,
    )


@feedback_router.post("")
def create_feedback(
    payload: CreateFeedbackSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Submit new customer feedback."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    user = (
        db.query(User)
        .filter(
            User.keycloak_id == context.keycloak_id, User.tenant_id == context.tenant_id
        )
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    feedback = Feedback(
        user_id=user.id,
        tenant_id=context.tenant_id,
        category=payload.category,
        subject=payload.subject,
        message=payload.message,
        rating=payload.rating,
        status=FeedbackStatus.OPEN,
    )

    try:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during create_feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

    return JSONResponse(
        content={
            "message": "Feedback submitted successfully",
            "feedback": feedback.to_dict(),
        },
        status_code=201,
    )


@feedback_router.get("/summary")
def get_feedback_summary(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get feedback summary statistics for the tenant."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    feedbacks = db.query(Feedback).filter(Feedback.tenant_id == context.tenant_id).all()

    total = len(feedbacks)
    status_counts = {s.value: 0 for s in FeedbackStatus}
    category_counts = {c.value: 0 for c in FeedbackCategory}
    ratings = [f.rating for f in feedbacks if f.rating is not None]

    for f in feedbacks:
        if f.status:
            status_counts[f.status.value] += 1
        if f.category:
            category_counts[f.category.value] += 1

    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    return JSONResponse(
        content={
            "message": "success",
            "summary": {
                "total": total,
                "by_status": status_counts,
                "by_category": category_counts,
                "average_rating": avg_rating,
                "rated_count": len(ratings),
            },
        },
        status_code=200,
    )


@feedback_router.get("/{feedback_id}")
def get_feedback(
    feedback_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get a specific feedback by ID."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    feedback = (
        db.query(Feedback)
        .filter(Feedback.id == feedback_id, Feedback.tenant_id == context.tenant_id)
        .first()
    )

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return JSONResponse(
        content={
            "message": "success",
            "feedback": feedback.to_dict(),
        },
        status_code=200,
    )


@feedback_router.post("/{feedback_id}/respond")
def respond_to_feedback(
    feedback_id: str,
    payload: RespondToFeedbackSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Respond to a customer feedback."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    feedback = (
        db.query(Feedback)
        .filter(Feedback.id == feedback_id, Feedback.tenant_id == context.tenant_id)
        .first()
    )

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if feedback.status == FeedbackStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot respond to closed feedback")

    feedback.response = payload.response
    feedback.responded_by = context.keycloak_id
    feedback.responded_at = datetime.datetime.now(datetime.timezone.utc)

    # Update status
    try:
        new_status = (
            FeedbackStatus(payload.status)
            if payload.status
            else FeedbackStatus.RESOLVED
        )
        feedback.status = new_status
    except ValueError:
        feedback.status = FeedbackStatus.RESOLVED

    try:
        db.commit()
        db.refresh(feedback)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during respond_to_feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save response")

    return JSONResponse(
        content={
            "message": "Response submitted successfully",
            "feedback": feedback.to_dict(),
        },
        status_code=200,
    )
