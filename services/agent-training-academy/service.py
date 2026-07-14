"""
Agent Training Academy - Learning Management System (LMS)
Provides structured training, certification, and continuous education for agents.
Features: Course management, video lessons, quizzes, certifications, progress tracking,
gamified learning paths, CBN mandatory compliance training, and performance-linked bonuses.
"""
import logging
import random
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from models import (
    Course, Lesson, Quiz, QuizQuestion, QuizAttempt, QuizAnswer,
    Enrollment, LessonProgress, Certificate, LearningPath,
    LearningPathCourse, CourseStatus, EnrollmentStatus, CertificateStatus
)
from config import settings

logger = logging.getLogger(__name__)

# CBN mandatory training course codes
CBN_MANDATORY_COURSES = [
    "CBN-AML-001",    # Anti-Money Laundering
    "CBN-KYC-001",    # Know Your Customer
    "CBN-FRAUD-001",  # Fraud Prevention
    "CBN-DATA-001",   # Data Protection (NDPR)
    "CBN-AGENT-001",  # Agent Banking Guidelines
]

# Passing score threshold
QUIZ_PASS_THRESHOLD = 70.0  # 70%
CERTIFICATE_VALIDITY_DAYS = 365  # 1 year


class AgentTrainingAcademyService:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # COURSE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def create_course(
        self,
        title: str,
        description: str,
        course_code: str,
        category: str,
        difficulty_level: str,
        estimated_duration_minutes: int,
        is_mandatory: bool = False,
        is_cbn_required: bool = False,
        passing_score: float = QUIZ_PASS_THRESHOLD,
        created_by: Optional[UUID] = None,
    ) -> Course:
        course = Course(
            title=title,
            description=description,
            course_code=course_code,
            category=category,
            difficulty_level=difficulty_level,
            estimated_duration_minutes=estimated_duration_minutes,
            is_mandatory=is_mandatory,
            is_cbn_required=is_cbn_required,
            passing_score=passing_score,
            status="draft",
            created_by=created_by,
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def publish_course(self, course_id: UUID) -> Course:
        course = self._get_course(course_id)
        lessons = self.db.query(Lesson).filter(Lesson.course_id == course_id).count()
        if lessons == 0:
            raise ValueError("Cannot publish a course with no lessons")
        course.status = "published"
        course.published_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(course)
        return course

    def add_lesson(
        self,
        course_id: UUID,
        title: str,
        content_type: str,
        content_url: Optional[str],
        content_text: Optional[str],
        duration_minutes: int,
        order_index: int,
        is_mandatory: bool = True,
    ) -> Lesson:
        self._get_course(course_id)
        lesson = Lesson(
            course_id=course_id,
            title=title,
            content_type=content_type,
            content_url=content_url,
            content_text=content_text,
            duration_minutes=duration_minutes,
            order_index=order_index,
            is_mandatory=is_mandatory,
        )
        self.db.add(lesson)
        self.db.commit()
        self.db.refresh(lesson)
        return lesson

    def add_quiz(
        self,
        course_id: UUID,
        title: str,
        questions: List[Dict],
        max_attempts: int = 3,
        time_limit_minutes: Optional[int] = None,
    ) -> Quiz:
        quiz = Quiz(
            course_id=course_id,
            title=title,
            max_attempts=max_attempts,
            time_limit_minutes=time_limit_minutes,
            total_questions=len(questions),
            passing_score=QUIZ_PASS_THRESHOLD,
        )
        self.db.add(quiz)
        self.db.flush()

        for i, q in enumerate(questions):
            question = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q["question"],
                question_type=q.get("type", "multiple_choice"),
                options=q.get("options", []),
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                points=q.get("points", 1),
                order_index=i,
            )
            self.db.add(question)

        self.db.commit()
        self.db.refresh(quiz)
        return quiz

    # ─────────────────────────────────────────────────────────────────────────
    # ENROLLMENT & PROGRESS
    # ─────────────────────────────────────────────────────────────────────────

    def enroll_agent(self, agent_id: UUID, course_id: UUID) -> Enrollment:
        """Enroll an agent in a course."""
        existing = self.db.query(Enrollment).filter(
            and_(Enrollment.agent_id == agent_id, Enrollment.course_id == course_id)
        ).first()
        if existing:
            return existing

        course = self._get_course(course_id)
        enrollment = Enrollment(
            agent_id=agent_id,
            course_id=course_id,
            status="enrolled",
            enrolled_at=datetime.now(timezone.utc),
            due_date=(datetime.now(timezone.utc) + timedelta(days=30)) if course.is_mandatory else None,
        )
        self.db.add(enrollment)
        self.db.commit()
        self.db.refresh(enrollment)
        logger.info(f"Agent {agent_id} enrolled in course {course_id}")
        return enrollment

    def enroll_in_mandatory_courses(self, agent_id: UUID) -> List[Enrollment]:
        """Auto-enroll a new agent in all mandatory CBN courses."""
        enrollments = []
        mandatory_courses = self.db.query(Course).filter(
            and_(Course.is_mandatory == True, Course.status == "published")
        ).all()
        for course in mandatory_courses:
            enrollment = self.enroll_agent(agent_id, course.id)
            enrollments.append(enrollment)
        return enrollments

    def mark_lesson_complete(
        self,
        agent_id: UUID,
        lesson_id: UUID,
        time_spent_seconds: int,
    ) -> LessonProgress:
        lesson = self.db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise ValueError(f"Lesson {lesson_id} not found")

        progress = self.db.query(LessonProgress).filter(
            and_(LessonProgress.agent_id == agent_id, LessonProgress.lesson_id == lesson_id)
        ).first()

        if not progress:
            progress = LessonProgress(
                agent_id=agent_id,
                lesson_id=lesson_id,
                course_id=lesson.course_id,
                status="completed",
                time_spent_seconds=time_spent_seconds,
                completed_at=datetime.now(timezone.utc),
            )
            self.db.add(progress)
        else:
            progress.status = "completed"
            progress.time_spent_seconds += time_spent_seconds
            progress.completed_at = datetime.now(timezone.utc)

        self.db.flush()

        # Update enrollment progress
        self._update_enrollment_progress(agent_id, lesson.course_id)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def _update_enrollment_progress(self, agent_id: UUID, course_id: UUID) -> None:
        """Recalculate and update enrollment completion percentage."""
        total_lessons = self.db.query(Lesson).filter(
            and_(Lesson.course_id == course_id, Lesson.is_mandatory == True)
        ).count()
        completed_lessons = self.db.query(LessonProgress).filter(
            and_(
                LessonProgress.agent_id == agent_id,
                LessonProgress.course_id == course_id,
                LessonProgress.status == "completed",
            )
        ).count()

        enrollment = self.db.query(Enrollment).filter(
            and_(Enrollment.agent_id == agent_id, Enrollment.course_id == course_id)
        ).first()

        if enrollment and total_lessons > 0:
            enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
            if enrollment.progress_percentage >= 100 and enrollment.status == "enrolled":
                enrollment.status = "completed"
                enrollment.completed_at = datetime.now(timezone.utc)

    # ─────────────────────────────────────────────────────────────────────────
    # QUIZ ATTEMPTS
    # ─────────────────────────────────────────────────────────────────────────

    def start_quiz_attempt(self, agent_id: UUID, quiz_id: UUID) -> QuizAttempt:
        quiz = self.db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise ValueError(f"Quiz {quiz_id} not found")

        # Check attempt limit
        attempts_used = self.db.query(QuizAttempt).filter(
            and_(QuizAttempt.agent_id == agent_id, QuizAttempt.quiz_id == quiz_id)
        ).count()
        if attempts_used >= quiz.max_attempts:
            raise ValueError(f"Maximum attempts ({quiz.max_attempts}) reached for this quiz")

        attempt = QuizAttempt(
            agent_id=agent_id,
            quiz_id=quiz_id,
            course_id=quiz.course_id,
            attempt_number=attempts_used + 1,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
            time_limit_expires_at=(
                datetime.now(timezone.utc) + timedelta(minutes=quiz.time_limit_minutes)
                if quiz.time_limit_minutes else None
            ),
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def submit_quiz_attempt(
        self,
        attempt_id: UUID,
        answers: List[Dict],
    ) -> Tuple[QuizAttempt, Optional["Certificate"]]:
        """Submit quiz answers and calculate score."""
        attempt = self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        if attempt.status != "in_progress":
            raise ValueError("Attempt is not in progress")

        # Check time limit
        if attempt.time_limit_expires_at and datetime.now(timezone.utc) > attempt.time_limit_expires_at:
            attempt.status = "timed_out"
            self.db.commit()
            raise ValueError("Quiz time limit exceeded")

        quiz = self.db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
        questions = self.db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == attempt.quiz_id
        ).order_by(QuizQuestion.order_index).all()

        total_points = sum(q.points for q in questions)
        earned_points = 0

        for answer_data in answers:
            question = next((q for q in questions if str(q.id) == str(answer_data.get("question_id"))), None)
            if not question:
                continue
            is_correct = str(answer_data.get("answer", "")).strip().lower() == str(question.correct_answer).strip().lower()
            if is_correct:
                earned_points += question.points

            qa = QuizAnswer(
                attempt_id=attempt_id,
                question_id=question.id,
                given_answer=str(answer_data.get("answer", "")),
                is_correct=is_correct,
                points_earned=question.points if is_correct else 0,
            )
            self.db.add(qa)

        score_percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        passed = score_percentage >= quiz.passing_score

        attempt.status = "completed"
        attempt.score_percentage = score_percentage
        attempt.earned_points = earned_points
        attempt.total_points = total_points
        attempt.passed = passed
        attempt.completed_at = datetime.now(timezone.utc)

        self.db.flush()

        # Issue certificate if passed
        certificate = None
        if passed:
            certificate = self._issue_certificate(attempt.agent_id, attempt.course_id, score_percentage)

        self.db.commit()
        self.db.refresh(attempt)
        return attempt, certificate

    # ─────────────────────────────────────────────────────────────────────────
    # CERTIFICATES
    # ─────────────────────────────────────────────────────────────────────────

    def _issue_certificate(
        self,
        agent_id: UUID,
        course_id: UUID,
        score: float,
    ) -> Certificate:
        """Issue a certificate upon course completion."""
        # Check if certificate already exists
        existing = self.db.query(Certificate).filter(
            and_(
                Certificate.agent_id == agent_id,
                Certificate.course_id == course_id,
                Certificate.status == "active",
            )
        ).first()
        if existing:
            return existing

        course = self._get_course(course_id)
        cert_number = self._generate_cert_number(course.course_code)
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(days=CERTIFICATE_VALIDITY_DAYS)

        cert = Certificate(
            agent_id=agent_id,
            course_id=course_id,
            certificate_number=cert_number,
            score=score,
            status="active",
            issued_at=issued_at,
            expires_at=expires_at,
            course_title=course.title,
            is_cbn_required=course.is_cbn_required,
        )
        self.db.add(cert)
        self.db.flush()
        logger.info(f"Certificate {cert_number} issued to agent {agent_id} for course {course_id}")
        return cert

    def _generate_cert_number(self, course_code: str) -> str:
        year = datetime.now().year
        random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"54L-{course_code}-{year}-{random_part}"

    def get_agent_certificates(self, agent_id: UUID) -> List[Certificate]:
        return self.db.query(Certificate).filter(
            Certificate.agent_id == agent_id
        ).order_by(Certificate.issued_at.desc()).all()

    def revoke_certificate(self, cert_id: UUID, reason: str = "") -> Certificate:
        cert = self.db.query(Certificate).filter(Certificate.id == cert_id).first()
        if not cert:
            raise ValueError(f"Certificate {cert_id} not found")
        if cert.status == "revoked":
            raise ValueError("Certificate is already revoked")
        cert.status = "revoked"
        self.db.commit()
        self.db.refresh(cert)
        logger.info(f"Certificate {cert.certificate_number} revoked. Reason: {reason}")
        return cert

    def renew_certificate(self, cert_id: UUID) -> Certificate:
        old = self.db.query(Certificate).filter(Certificate.id == cert_id).first()
        if not old:
            raise ValueError(f"Certificate {cert_id} not found")
        old.status = "renewed"
        cert_number = self._generate_cert_number(old.certificate_number.split("-")[1] if "-" in old.certificate_number else "RNW")
        issued_at = datetime.now(timezone.utc)
        new_cert = Certificate(
            agent_id=old.agent_id,
            course_id=old.course_id,
            certificate_number=cert_number,
            score=old.score,
            status="active",
            course_title=old.course_title,
            is_cbn_required=old.is_cbn_required,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(days=CERTIFICATE_VALIDITY_DAYS),
        )
        self.db.add(new_cert)
        self.db.commit()
        self.db.refresh(new_cert)
        logger.info(f"Certificate {old.certificate_number} renewed as {new_cert.certificate_number}")
        return new_cert

    def get_agent_compliance_status(self, agent_id: UUID) -> Dict:
        """Check if agent has completed all CBN mandatory training."""
        mandatory_courses = self.db.query(Course).filter(
            and_(Course.is_cbn_required == True, Course.status == "published")
        ).all()

        completed = []
        pending = []
        overdue = []
        now = datetime.now(timezone.utc)

        for course in mandatory_courses:
            cert = self.db.query(Certificate).filter(
                and_(
                    Certificate.agent_id == agent_id,
                    Certificate.course_id == course.id,
                    Certificate.status == "active",
                    Certificate.expires_at > now,
                )
            ).first()

            enrollment = self.db.query(Enrollment).filter(
                and_(Enrollment.agent_id == agent_id, Enrollment.course_id == course.id)
            ).first()

            if cert:
                completed.append({"course_code": course.course_code, "title": course.title, "cert_number": cert.certificate_number})
            elif enrollment and enrollment.due_date and enrollment.due_date < now:
                overdue.append({"course_code": course.course_code, "title": course.title, "due_date": enrollment.due_date.isoformat()})
            else:
                pending.append({"course_code": course.course_code, "title": course.title})

        return {
            "agent_id": str(agent_id),
            "is_fully_compliant": len(pending) == 0 and len(overdue) == 0,
            "completed_count": len(completed),
            "pending_count": len(pending),
            "overdue_count": len(overdue),
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
        }

    def get_agent_dashboard(self, agent_id: UUID) -> Dict:
        """Get agent's full learning dashboard."""
        enrollments = self.db.query(Enrollment).filter(
            Enrollment.agent_id == agent_id
        ).all()
        certificates = self.get_agent_certificates(agent_id)
        compliance = self.get_agent_compliance_status(agent_id)

        in_progress = [e for e in enrollments if e.status == "enrolled"]
        completed_courses = [e for e in enrollments if e.status == "completed"]

        return {
            "agent_id": str(agent_id),
            "total_enrolled": len(enrollments),
            "in_progress": len(in_progress),
            "completed": len(completed_courses),
            "certificates_earned": len(certificates),
            "cbn_compliance": compliance,
            "enrollments": [
                {
                    "course_id": str(e.course_id),
                    "status": e.status,
                    "progress_percentage": float(e.progress_percentage or 0),
                    "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
                    "due_date": e.due_date.isoformat() if e.due_date else None,
                }
                for e in enrollments
            ],
        }

    def list_courses(self, skip: int = 0, limit: int = 50) -> List[Course]:
        return self.db.query(Course).order_by(Course.created_at.desc()).offset(skip).limit(limit).all()

    def list_all_certificates(self, skip: int = 0, limit: int = 50, status: str = None) -> Dict:
        q = self.db.query(Certificate)
        if status:
            q = q.filter(Certificate.status == status)
        total = q.count()
        certs = q.order_by(Certificate.issued_at.desc()).offset(skip).limit(limit).all()
        return {
            "certificates": [
                {
                    "id": str(c.id),
                    "certificate_number": c.certificate_number,
                    "agent_id": str(c.agent_id),
                    "course_id": str(c.course_id),
                    "course_title": c.course_title,
                    "score": float(c.score) if c.score else None,
                    "status": c.status,
                    "is_cbn_required": c.is_cbn_required,
                    "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                }
                for c in certs
            ],
            "total": total,
        }

    def get_cert_stats(self) -> Dict:
        now = datetime.now(timezone.utc)
        soon = now + timedelta(days=30)
        active = self.db.query(Certificate).filter(Certificate.status == "active").count()
        expiring_soon = self.db.query(Certificate).filter(
            Certificate.status == "active",
            Certificate.expires_at <= soon,
            Certificate.expires_at > now,
        ).count()
        revoked = self.db.query(Certificate).filter(Certificate.status == "revoked").count()
        total = self.db.query(Certificate).count()
        renewed = self.db.query(Certificate).filter(Certificate.status == "renewed").count()
        renewal_rate = round((renewed + active) / max(total, 1) * 100, 1)
        return {
            "active": active,
            "expiring_soon": expiring_soon,
            "revoked": revoked,
            "total": total,
            "renewal_rate": renewal_rate,
        }

    def get_recent_enrollments(self, limit: int = 20) -> List[Dict]:
        enrollments = (
            self.db.query(Enrollment, Course)
            .join(Course, Enrollment.course_id == Course.id)
            .order_by(Enrollment.enrolled_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "agent_id": str(e.agent_id),
                "course_id": str(e.course_id),
                "course": c.title,
                "status": e.status,
                "progress": float(e.progress_percentage or 0),
                "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "due_date": e.due_date.isoformat() if e.due_date else None,
            }
            for e, c in enrollments
        ]

    def get_course(self, course_id: UUID) -> Course:
        return self._get_course(course_id)

    def get_stats(self) -> Dict:
        total_courses = self.db.query(Course).count()
        mandatory_courses = self.db.query(Course).filter(Course.is_mandatory == True).count()
        total_enrollments = self.db.query(Enrollment).count()
        total_completions = self.db.query(Enrollment).filter(Enrollment.status == "completed").count()
        total_certificates = self.db.query(Certificate).count()
        avg_pass_rate_result = self.db.query(func.avg(QuizAttempt.score_percentage)).filter(
            QuizAttempt.passed == True
        ).scalar()
        return {
            "total_courses": total_courses,
            "total_enrollments": total_enrollments,
            "total_completions": total_completions,
            "total_certificates": total_certificates,
            "avg_pass_rate": round(float(avg_pass_rate_result or 0), 1),
            "mandatory_courses": mandatory_courses,
        }

    def _get_course(self, course_id: UUID) -> Course:
        course = self.db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise ValueError(f"Course {course_id} not found")
        return course
