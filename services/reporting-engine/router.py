import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models, config
from .models import (
    ReportTemplate,
    ReportSchedule,
    ReportInstance,
)
from .models import (
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateRead,
    ReportScheduleCreate,
    ReportScheduleUpdate,
    ReportScheduleRead,
    ReportInstanceRead,
    ReportGenerationRequest,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Router
router = APIRouter(prefix="/reports", tags=["Reporting Engine"])

# Dependency to get the database session
get_db = config.get_db

# Directory where generated report artifacts are actually persisted.
REPORT_STORAGE_DIR = os.getenv("REPORT_STORAGE_DIR", "/var/reports")


# --- Utility Functions (Business Logic) ---
def _fetch_report_data(db: Session, template: ReportTemplate, runtime_data: dict = None) -> list:
    """Fetch report rows by executing the template's data source query.

    Raises RuntimeError when the template has no data source configured; the
    caller records the instance as FAILED with the real error message.
    """
    if not template.data_source_query:
        raise RuntimeError(
            f"Template '{template.name}' has no data_source_query configured"
        )
    result = db.execute(text(template.data_source_query), runtime_data or {})
    columns = list(result.keys())
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _render_report(template: ReportTemplate, rows: list, output_format: str, runtime_data: dict = None) -> bytes:
    """Render the template content with the fetched rows in the requested format."""
    context = {
        "rows": rows,
        "row_count": len(rows),
        "generated_at": datetime.utcnow().isoformat(),
        **(runtime_data or {}),
    }
    try:
        from jinja2 import Template
    except ImportError:
        raise RuntimeError("Jinja2 is not installed; cannot render report templates")
    rendered = Template(template.template_content).render(**context)

    fmt = (output_format or "").upper()
    if fmt == "CSV":
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return buf.getvalue().encode("utf-8")
    if fmt == "JSON":
        return json.dumps(
            {
                "template": template.name,
                "generated_at": context["generated_at"],
                "row_count": len(rows),
                "rows": rows,
            },
            indent=2,
            default=str,
        ).encode("utf-8")
    if fmt == "HTML":
        return rendered.encode("utf-8")
    if fmt == "PDF":
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            raise RuntimeError("ReportLab is not installed; cannot render PDF reports")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        y = 750
        for line in (rendered.splitlines() or [""]):
            c.drawString(40, y, line[:110])
            y -= 14
            if y < 40:
                c.showPage()
                y = 750
        c.save()
        return buf.getvalue()
    raise RuntimeError(f"Unsupported output format: {output_format}")


def _store_report_file(template: ReportTemplate, content: bytes, output_format: str) -> str:
    """Persist the rendered report and return the real path it was written to."""
    os.makedirs(REPORT_STORAGE_DIR, exist_ok=True)
    safe_name = template.name.replace(" ", "_")
    file_path = os.path.join(
        REPORT_STORAGE_DIR,
        f"{safe_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{output_format.lower()}",
    )
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path


def _generate_report_generation(
    db: Session,
    template: ReportTemplate,
    output_format: str,
    schedule_id: UUID = None,
    runtime_data: dict = None,
) -> ReportInstance:
    """Real report pipeline: query data source -> render template -> store file.

    There is no simulated work and no random failure injection. Any failure
    raises and is recorded as a FAILED instance with the real error message,
    and file_path only ever points at a file that was actually written.
    """
    logger.info(
        f"Generating report for template {template.id} in format {output_format}"
    )
    try:
        rows = _fetch_report_data(db, template, runtime_data)
        content = _render_report(template, rows, output_format, runtime_data)
        file_path = _store_report_file(template, content, output_format)
        status_val = "COMPLETED"
        error_msg = None
    except Exception as exc:
        logger.error(f"Report generation failed for template {template.id}: {exc}")
        status_val = "FAILED"
        error_msg = str(exc)
        file_path = None

    # Create and return a new ReportInstance object (not yet saved to DB)
    instance = ReportInstance(
        template_id=template.id,
        schedule_id=schedule_id,
        status=status_val,
        output_format=output_format,
        file_path=file_path,
        generated_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        error_message=error_msg,
    )
    return instance


def _calculate_next_run(schedule_type: str) -> datetime:
    """Generates calculating the next run time based on schedule type."""
    now = datetime.utcnow()
    if schedule_type == "DAILY":
        return now + timedelta(days=1)
    elif schedule_type == "WEEKLY":
        return now + timedelta(weeks=1)
    elif schedule_type == "MONTHLY":
        return now + timedelta(days=30)  # Approximation
    elif schedule_type == "ONCE":
        return now + timedelta(minutes=5) # Run once in 5 minutes
    return now + timedelta(days=1)


# --- Report Template Endpoints ---
@router.post(
    "/templates",
    response_model=ReportTemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new report template",
)
def create_template(
    template_in: ReportTemplateCreate, db: Session = Depends(get_db)
):
    """
    Creates a new report template definition.
    """
    db_template = ReportTemplate(**template_in.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    logger.info(f"Created new template: {db_template.id}")
    return db_template


@router.get(
    "/templates",
    response_model=List[ReportTemplateRead],
    summary="Retrieve all report templates",
)
def read_templates(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of all report templates.
    """
    templates = db.query(ReportTemplate).offset(skip).limit(limit).all()
    return templates


@router.get(
    "/templates/{template_id}",
    response_model=ReportTemplateRead,
    summary="Retrieve a specific report template",
)
def read_template(template_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single report template by its ID.
    Raises 404 if the template is not found.
    """
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report Template not found"
        )
    return template


@router.put(
    "/templates/{template_id}",
    response_model=ReportTemplateRead,
    summary="Update an existing report template",
)
def update_template(
    template_id: UUID,
    template_in: ReportTemplateUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing report template by its ID.
    """
    db_template = read_template(template_id=template_id, db=db)  # Reuses the read logic for 404 check
    update_data = template_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    logger.info(f"Updated template: {db_template.id}")
    return db_template


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report template",
)
def delete_template(template_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a report template and all associated schedules and instances.
    """
    db_template = read_template(template_id=template_id, db=db)
    db.delete(db_template)
    db.commit()
    logger.info(f"Deleted template: {template_id}")
    return {"ok": True}


# --- Report Schedule Endpoints ---
@router.post(
    "/schedules",
    response_model=ReportScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new report schedule",
)
def create_schedule(
    schedule_in: ReportScheduleCreate, db: Session = Depends(get_db)
):
    """
    Creates a new schedule for a report template.
    Automatically calculates the initial `next_run_at`.
    """
    # Check if template exists
    template = db.query(ReportTemplate).filter(ReportTemplate.id == schedule_in.template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    next_run = _calculate_next_run(schedule_in.schedule_type)

    db_schedule = ReportSchedule(
        **schedule_in.model_dump(), next_run_at=next_run
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    logger.info(f"Created new schedule: {db_schedule.id} for template {template.id}")
    return db_schedule


@router.get(
    "/schedules",
    response_model=List[ReportScheduleRead],
    summary="Retrieve all report schedules",
)
def read_schedules(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of all report schedules.
    """
    schedules = db.query(ReportSchedule).offset(skip).limit(limit).all()
    return schedules


@router.get(
    "/schedules/{schedule_id}",
    response_model=ReportScheduleRead,
    summary="Retrieve a specific report schedule",
)
def read_schedule(schedule_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single report schedule by its ID.
    """
    schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report Schedule not found"
        )
    return schedule


@router.put(
    "/schedules/{schedule_id}",
    response_model=ReportScheduleRead,
    summary="Update an existing report schedule",
)
def update_schedule(
    schedule_id: UUID,
    schedule_in: ReportScheduleUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing report schedule by its ID.
    If `schedule_type` is updated, `next_run_at` is recalculated.
    """
    db_schedule = read_schedule(schedule_id=schedule_id, db=db)
    update_data = schedule_in.model_dump(exclude_unset=True)

    # If schedule_type is being updated, recalculate next_run_at
    if "schedule_type" in update_data:
        update_data["next_run_at"] = _calculate_next_run(update_data["schedule_type"])

    for key, value in update_data.items():
        setattr(db_schedule, key, value)

    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    logger.info(f"Updated schedule: {db_schedule.id}")
    return db_schedule


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report schedule",
)
def delete_schedule(schedule_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a report schedule.
    """
    db_schedule = read_schedule(schedule_id=schedule_id, db=db)
    db.delete(db_schedule)
    db.commit()
    logger.info(f"Deleted schedule: {schedule_id}")
    return {"ok": True}


# --- Report Instance Endpoints ---
@router.get(
    "/instances",
    response_model=List[ReportInstanceRead],
    summary="Retrieve all report instances",
)
def read_instances(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of all generated report instances.
    """
    instances = db.query(ReportInstance).offset(skip).limit(limit).all()
    return instances


@router.get(
    "/instances/{instance_id}",
    response_model=ReportInstanceRead,
    summary="Retrieve a specific report instance",
)
def read_instance(instance_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single report instance by its ID.
    """
    instance = db.query(ReportInstance).filter(ReportInstance.id == instance_id).first()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report Instance not found"
        )
    return instance


# --- Business Logic Endpoints ---
@router.post(
    "/generate",
    response_model=ReportInstanceRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a report on demand",
)
def generate_report_on_demand(
    request: ReportGenerationRequest, db: Session = Depends(get_db)
):
    """
    Triggers an immediate, on-demand generation of a report based on a template.
    The process is generated to be asynchronous, returning the PENDING instance immediately.
    """
    template = read_template(template_id=request.template_id, db=db)

    # 1. Create a PENDING instance in the database
    pending_instance = ReportInstance(
        template_id=template.id,
        schedule_id=None,
        status="PENDING",
        output_format=request.output_format,
        generated_at=datetime.utcnow(),
    )
    db.add(pending_instance)
    db.commit()
    db.refresh(pending_instance)

    # 2. Execute the real generation pipeline (query -> render -> store)
    generated_instance = _generate_report_generation(
        db=db,
        template=template,
        output_format=request.output_format,
        runtime_data=request.runtime_data,
    )

    # 3. Update the instance with the result
    db_instance = db.query(ReportInstance).filter(ReportInstance.id == pending_instance.id).first()
    if db_instance:
        db_instance.status = generated_instance.status
        db_instance.file_path = generated_instance.file_path
        db_instance.completed_at = generated_instance.completed_at
        db_instance.error_message = generated_instance.error_message
        db.add(db_instance)
        db.commit()
        db.refresh(db_instance)
        logger.info(f"Report instance {db_instance.id} finished with status: {db_instance.status}")
        return db_instance

    # Should not happen if the initial commit succeeded
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update report instance after generation.")


@router.get(
    "/instances/{instance_id}/download",
    summary="Download the generated report file",
)
def download_report(instance_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves the generated report file for a given instance ID.

    Only files that were actually written by the generation pipeline are
    served. If the artifact is missing from storage this is a 404 - we never
    synthesize placeholder content and serve it as a PDF/CSV.
    """
    instance = read_instance(instance_id=instance_id, db=db)

    if instance.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report generation is not complete. Current status: {instance.status}",
        )

    if not instance.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File path not found for this completed report instance.",
        )

    if not os.path.exists(instance.file_path):
        logger.error(f"Report artifact missing from storage: {instance.file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report artifact not found in storage.",
        )

    media_type_map = {
        "PDF": "application/pdf",
        "CSV": "text/csv",
        "JSON": "application/json",
        "HTML": "text/html",
    }
    media_type = media_type_map.get(instance.output_format, "application/octet-stream")
    filename = f"report_{instance_id}.{instance.output_format.lower()}"

    return FileResponse(
        path=instance.file_path,
        media_type=media_type,
        filename=filename,
    )
