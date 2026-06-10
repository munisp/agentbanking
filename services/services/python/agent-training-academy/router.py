"""API Router for Agent Training Academy LMS."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import (CreateCourseRequest, AddLessonRequest, AddQuizRequest,
                     SubmitQuizRequest, MarkLessonCompleteRequest)
from service import AgentTrainingAcademyService
from config import get_db

router = APIRouter(prefix="/api/v1/training", tags=["Agent Training Academy"])


def get_svc(db: Session = Depends(get_db)) -> AgentTrainingAcademyService:
    return AgentTrainingAcademyService(db)


# ── Courses ──────────────────────────────────────────────────────────────────
@router.post("/courses", summary="Create a new training course")
def create_course(payload: CreateCourseRequest, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.create_course(**payload.model_dump())


@router.post("/courses/{course_id}/publish")
def publish_course(course_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    try:
        return svc.publish_course(course_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/courses/{course_id}/lessons")
def add_lesson(course_id: UUID, payload: AddLessonRequest, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.add_lesson(course_id=course_id, **payload.model_dump())


@router.post("/courses/{course_id}/quiz")
def add_quiz(course_id: UUID, payload: AddQuizRequest, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.add_quiz(course_id=course_id, **payload.model_dump())


# ── Enrollment ───────────────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/enroll/{course_id}")
def enroll(agent_id: UUID, course_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    try:
        return svc.enroll_agent(agent_id, course_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/agents/{agent_id}/enroll-mandatory")
def enroll_mandatory(agent_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.enroll_in_mandatory_courses(agent_id)


# ── Progress ─────────────────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/lessons/{lesson_id}/complete")
def complete_lesson(agent_id: UUID, lesson_id: UUID, payload: MarkLessonCompleteRequest, svc: AgentTrainingAcademyService = Depends(get_svc)):
    try:
        return svc.mark_lesson_complete(agent_id, lesson_id, payload.time_spent_seconds)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Quizzes ───────────────────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/quizzes/{quiz_id}/start")
def start_quiz(agent_id: UUID, quiz_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    try:
        return svc.start_quiz_attempt(agent_id, quiz_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/attempts/{attempt_id}/submit")
def submit_quiz(attempt_id: UUID, payload: SubmitQuizRequest, svc: AgentTrainingAcademyService = Depends(get_svc)):
    try:
        attempt, cert = svc.submit_quiz_attempt(attempt_id, payload.answers)
        return {"attempt": attempt, "certificate": cert}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Certificates & Compliance ─────────────────────────────────────────────────
@router.get("/agents/{agent_id}/certificates")
def get_certificates(agent_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.get_agent_certificates(agent_id)


@router.get("/agents/{agent_id}/compliance")
def get_compliance(agent_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.get_agent_compliance_status(agent_id)


@router.get("/agents/{agent_id}/dashboard")
def get_dashboard(agent_id: UUID, svc: AgentTrainingAcademyService = Depends(get_svc)):
    return svc.get_agent_dashboard(agent_id)


@router.get("/health")
def health():
    return {"status": "healthy", "service": "agent-training-academy"}
