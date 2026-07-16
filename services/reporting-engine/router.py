import logging
import random
import time
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
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


# --- Utility Functions (Business Logic) ---
def _generate_report_generation(
    template: ReportTemplate,
    output_format: str,
    schedule_id: UUID = None,
    runtime_data: dict = None,
) -> ReportInstance:
    """
    Generates the complex report generation process.
    In a real system, this would involve:
    1. Fetching data using template.data_source_query and runtime_data.
    2. Rendering the template.template_content (e.g., Jinja2) with the data.
    3. Converting the rendered output to the specified output_format (PDF, CSV, etc.).
    4. Storing the file in a storage system (e.g., S3, local disk).
    """
    logger.info(
        f"Simulating generation for template {template.id} in format {output_format}"
    )

    # Process result
    if random.random() < 0.1:  # 10% chance of failure
        status_val = "FAILED"
        error_msg = "Failure during data processing."
        file_path = None
        completed_at = datetime.utcnow()
    else:
        # Execute report generation
        time.sleep(random.uniform(0.5, 2.0))
        status_val = "COMPLETED"
        error_msg = None
        # Generate file path
        file_path = f"/var/reports/{template.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{output_format.lower()}"
        completed_at = datetime.utcnow()

    # Create and return a new ReportInstance object (not yet saved to DB)
    instance = ReportInstance(
        template_id=template.id,
        schedule_id=schedule_id,
        status=status_val,
        output_format=output_format,
        file_path=file_path,
        generated_at=datetime.utcnow(),
        completed_at=completed_at,
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

    # 2. Execute the generation process
    # For this synchronous API, we'll generate the completion immediately after the commit
    # to demonstrate the full flow.
    generated_instance = _generate_report_generation(
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

    # NOTE: In a real-world scenario, this file would be retrieved from S3/Cloud Storage.
    # Return the generated file.
    # We must ensure the file exists for FileResponse to work.
    
    # Create a dummy file for demonstration purposes
    dummy_file_path = f"/tmp/report_{instance_id}.{instance.output_format.lower()}"
    try:
        with open(dummy_file_path, "w") as f:
            f.write(f"--- Report Content ---\n")
            f.write(f"Instance ID: {instance_id}\n")
            f.write(f"Template ID: {instance.template_id}\n")
            f.write(f"Format: {instance.output_format}\n")
            f.write(f"Generated At: {instance.generated_at}\n")
            f.write(f"This is a generated report content for a {instance.output_format} file.\n")
    except Exception as e:
        logger.error(f"Failed to create dummy file: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create dummy file for download.")

    media_type_map = {
        "PDF": "application/pdf",
        "CSV": "text/csv",
        "JSON": "application/json",
        "HTML": "text/html",
    }
    media_type = media_type_map.get(instance.output_format, "application/octet-stream")
    filename = f"report_{instance_id}.{instance.output_format.lower()}"

    return FileResponse(
        path=dummy_file_path,
        media_type=media_type,
        filename=filename,
    )
