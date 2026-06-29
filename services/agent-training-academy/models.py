"""Models for Agent Training Academy LMS."""
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Course(Base):
    __tablename__ = "lms_courses"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    course_code = Column(String(50), unique=True, nullable=False, index=True)
    category = Column(String(100), index=True)
    difficulty_level = Column(String(20))  # beginner | intermediate | advanced
    estimated_duration_minutes = Column(Integer)
    is_mandatory = Column(Boolean, default=False)
    is_cbn_required = Column(Boolean, default=False)
    passing_score = Column(Float, default=70.0)
    status = Column(String(20), default="draft", index=True)
    thumbnail_url = Column(String(500))
    created_by = Column(PGUUID(as_uuid=True))
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Lesson(Base):
    __tablename__ = "lms_lessons"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    content_type = Column(String(20))  # video | text | pdf | interactive
    content_url = Column(String(500))
    content_text = Column(Text)
    duration_minutes = Column(Integer)
    order_index = Column(Integer, default=0)
    is_mandatory = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Quiz(Base):
    __tablename__ = "lms_quizzes"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(300))
    max_attempts = Column(Integer, default=3)
    time_limit_minutes = Column(Integer)
    total_questions = Column(Integer)
    passing_score = Column(Float, default=70.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class QuizQuestion(Base):
    __tablename__ = "lms_quiz_questions"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), default="multiple_choice")
    options = Column(JSONB, default=[])
    correct_answer = Column(Text)
    explanation = Column(Text)
    points = Column(Integer, default=1)
    order_index = Column(Integer, default=0)


class QuizAttempt(Base):
    __tablename__ = "lms_quiz_attempts"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    quiz_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    course_id = Column(PGUUID(as_uuid=True))
    attempt_number = Column(Integer)
    status = Column(String(20), default="in_progress")
    score_percentage = Column(Float)
    earned_points = Column(Integer)
    total_points = Column(Integer)
    passed = Column(Boolean)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    time_limit_expires_at = Column(DateTime(timezone=True))


class QuizAnswer(Base):
    __tablename__ = "lms_quiz_answers"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    attempt_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    question_id = Column(PGUUID(as_uuid=True))
    given_answer = Column(Text)
    is_correct = Column(Boolean)
    points_earned = Column(Integer, default=0)


class Enrollment(Base):
    __tablename__ = "lms_enrollments"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    course_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(20), default="enrolled", index=True)
    progress_percentage = Column(Float, default=0.0)
    enrolled_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))


class LessonProgress(Base):
    __tablename__ = "lms_lesson_progress"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    lesson_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    course_id = Column(PGUUID(as_uuid=True))
    status = Column(String(20), default="not_started")
    time_spent_seconds = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True))


class Certificate(Base):
    __tablename__ = "lms_certificates"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    course_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    certificate_number = Column(String(100), unique=True, nullable=False)
    score = Column(Float)
    status = Column(String(20), default="active")
    course_title = Column(String(300))
    is_cbn_required = Column(Boolean, default=False)
    issued_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))


class LearningPath(Base):
    __tablename__ = "lms_learning_paths"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(300))
    description = Column(Text)
    target_role = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LearningPathCourse(Base):
    __tablename__ = "lms_learning_path_courses"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    path_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    course_id = Column(PGUUID(as_uuid=True), nullable=False)
    order_index = Column(Integer, default=0)


# Pydantic schemas
class CreateCourseRequest(BaseModel):
    title: str
    description: Optional[str] = None
    course_code: str
    category: str
    difficulty_level: str = "beginner"
    estimated_duration_minutes: int = 60
    is_mandatory: bool = False
    is_cbn_required: bool = False
    passing_score: float = 70.0


class AddLessonRequest(BaseModel):
    title: str
    content_type: str
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    duration_minutes: int = 10
    order_index: int = 0
    is_mandatory: bool = True


class AddQuizRequest(BaseModel):
    title: str
    questions: List[Dict]
    max_attempts: int = 3
    time_limit_minutes: Optional[int] = None


class SubmitQuizRequest(BaseModel):
    answers: List[Dict]


class MarkLessonCompleteRequest(BaseModel):
    time_spent_seconds: int = 0


class CourseStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EnrollmentStatus:
    ENROLLED = "enrolled"
    COMPLETED = "completed"
    DROPPED = "dropped"


class CertificateStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
