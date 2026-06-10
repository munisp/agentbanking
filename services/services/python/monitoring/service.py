import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from . import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class ServiceException(HTTPException):
    """Base exception for the monitoring service."""
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)

class ServiceNotFound(ServiceException):
    def __init__(self, service_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )

class EndpointNotFound(ServiceException):
    def __init__(self, endpoint_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint with ID {endpoint_id} not found"
        )

class ServiceAlreadyExists(ServiceException):
    def __init__(self, name: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service with name '{name}' already exists"
        )

class EndpointAlreadyExists(ServiceException):
    def __init__(self, service_id: int, url: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Endpoint with URL '{url}' already exists for service ID {service_id}"
        )

# --- Service CRUD Operations ---

def get_service_by_id(db: Session, service_id: int) -> models.Service:
    """Retrieve a service by its ID."""
    service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not service:
        raise ServiceNotFound(service_id)
    return service

def get_service_by_name(db: Session, name: str) -> Optional[models.Service]:
    """Retrieve a service by its name."""
    return db.query(models.Service).filter(models.Service.name == name).first()

def get_all_services(db: Session, skip: int = 0, limit: int = 100) -> List[models.Service]:
    """Retrieve a list of all services."""
    return db.query(models.Service).offset(skip).limit(limit).all()

def create_service(db: Session, service: schemas.ServiceCreate) -> models.Service:
    """Create a new service."""
    if get_service_by_name(db, service.name):
        raise ServiceAlreadyExists(service.name)
        
    db_service = models.Service(**service.model_dump())
    
    try:
        db.add(db_service)
        db.commit()
        db.refresh(db_service)
        logger.info(f"Created new service: {db_service.name} (ID: {db_service.id})")
        return db_service
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating service: {e}")
        raise ServiceAlreadyExists(service.name)

def update_service(db: Session, service_id: int, service_update: schemas.ServiceUpdate) -> models.Service:
    """Update an existing service."""
    db_service = get_service_by_id(db, service_id)
    
    update_data = service_update.model_dump(exclude_unset=True)
    
    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != db_service.name:
        if get_service_by_name(db, update_data["name"]):
            raise ServiceAlreadyExists(update_data["name"])

    for key, value in update_data.items():
        setattr(db_service, key, value)
    
    try:
        db.commit()
        db.refresh(db_service)
        logger.info(f"Updated service ID: {service_id}")
        return db_service
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating service ID {service_id}: {e}")
        raise ServiceAlreadyExists(update_data.get("name", db_service.name))

def delete_service(db: Session, service_id: int) -> Dict[str, Any]:
    """Delete a service and all its associated endpoints and records."""
    db_service = get_service_by_id(db, service_id)
    
    db.delete(db_service)
    db.commit()
    logger.warning(f"Deleted service ID: {service_id}")
    return {"detail": f"Service ID {service_id} deleted successfully"}

# --- Endpoint CRUD Operations ---

def get_endpoint_by_id(db: Session, endpoint_id: int) -> models.Endpoint:
    """Retrieve an endpoint by its ID."""
    endpoint = db.query(models.Endpoint).filter(models.Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise EndpointNotFound(endpoint_id)
    return endpoint

def get_endpoints_for_service(db: Session, service_id: int, skip: int = 0, limit: int = 100) -> List[models.Endpoint]:
    """Retrieve all endpoints for a given service."""
    # Ensure service exists
    get_service_by_id(db, service_id)
    
    return db.query(models.Endpoint).filter(models.Endpoint.service_id == service_id).offset(skip).limit(limit).all()

def create_endpoint(db: Session, endpoint: schemas.EndpointCreate) -> models.Endpoint:
    """Create a new endpoint for a service."""
    # Ensure service exists
    get_service_by_id(db, endpoint.service_id)
    
    # Check for existing endpoint with same URL for the service
    existing_endpoint = db.query(models.Endpoint).filter(
        models.Endpoint.service_id == endpoint.service_id,
        models.Endpoint.url == endpoint.url
    ).first()
    
    if existing_endpoint:
        raise EndpointAlreadyExists(endpoint.service_id, endpoint.url)
        
    db_endpoint = models.Endpoint(**endpoint.model_dump())
    
    try:
        db.add(db_endpoint)
        db.commit()
        db.refresh(db_endpoint)
        logger.info(f"Created new endpoint: {db_endpoint.url} (ID: {db_endpoint.id}) for service ID {db_endpoint.service_id}")
        return db_endpoint
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating endpoint: {e}")
        raise EndpointAlreadyExists(endpoint.service_id, endpoint.url)

def update_endpoint(db: Session, endpoint_id: int, endpoint_update: schemas.EndpointUpdate) -> models.Endpoint:
    """Update an existing endpoint."""
    db_endpoint = get_endpoint_by_id(db, endpoint_id)
    
    update_data = endpoint_update.model_dump(exclude_unset=True)
    
    # Check for URL conflict if URL is being updated
    if "url" in update_data and update_data["url"] != db_endpoint.url:
        existing_endpoint = db.query(models.Endpoint).filter(
            models.Endpoint.service_id == db_endpoint.service_id,
            models.Endpoint.url == update_data["url"]
        ).first()
        if existing_endpoint:
            raise EndpointAlreadyExists(db_endpoint.service_id, update_data["url"])

    for key, value in update_data.items():
        setattr(db_endpoint, key, value)
    
    try:
        db.commit()
        db.refresh(db_endpoint)
        logger.info(f"Updated endpoint ID: {endpoint_id}")
        return db_endpoint
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating endpoint ID {endpoint_id}: {e}")
        raise EndpointAlreadyExists(db_endpoint.service_id, update_data.get("url", db_endpoint.url))

def delete_endpoint(db: Session, endpoint_id: int) -> Dict[str, Any]:
    """Delete an endpoint and all its associated monitor records."""
    db_endpoint = get_endpoint_by_id(db, endpoint_id)
    
    db.delete(db_endpoint)
    db.commit()
    logger.warning(f"Deleted endpoint ID: {endpoint_id}")
    return {"detail": f"Endpoint ID {endpoint_id} deleted successfully"}

# --- MonitorRecord Operations ---

def create_monitor_record(db: Session, record: schemas.MonitorRecordCreate) -> models.MonitorRecord:
    """Create a new monitor record for an endpoint."""
    # Ensure endpoint exists
    get_endpoint_by_id(db, record.endpoint_id)
    
    db_record = models.MonitorRecord(**record.model_dump())
    
    try:
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        logger.info(f"Created monitor record ID: {db_record.id} for endpoint ID: {db_record.endpoint_id}")
        
        # After creating a record, update the service status
        aggregate_service_status(db, db_record.endpoint.service_id)
        
        return db_record
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating monitor record: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create monitor record")

def get_monitor_records_for_endpoint(db: Session, endpoint_id: int, skip: int = 0, limit: int = 100) -> List[models.MonitorRecord]:
    """Retrieve a list of monitor records for a given endpoint."""
    # Ensure endpoint exists
    get_endpoint_by_id(db, endpoint_id)
    
    return db.query(models.MonitorRecord).filter(models.MonitorRecord.endpoint_id == endpoint_id).order_by(models.MonitorRecord.timestamp.desc()).offset(skip).limit(limit).all()

# --- Status Aggregation Logic ---

def aggregate_service_status(db: Session, service_id: int) -> None:
    """
    Aggregates the status of a service based on the latest check of its active endpoints.
    - If any active endpoint has a failed check, status is 'Degraded'.
    - If all active endpoints have failed checks, status is 'Offline'.
    - Otherwise, status is 'Operational'.
    """
    db_service = get_service_by_id(db, service_id)
    active_endpoints = db.query(models.Endpoint).filter(
        models.Endpoint.service_id == service_id,
        models.Endpoint.is_active == True
    ).all()
    
    if not active_endpoints:
        # No active endpoints, assume operational or keep current status
        new_status = "Operational"
    else:
        failed_count = 0
        total_active = len(active_endpoints)
        
        for endpoint in active_endpoints:
            latest_record = db.query(models.MonitorRecord).filter(
                models.MonitorRecord.endpoint_id == endpoint.id
            ).order_by(models.MonitorRecord.timestamp.desc()).first()
            
            if latest_record and not latest_record.is_success:
                failed_count += 1
        
        if failed_count == total_active:
            new_status = "Offline"
        elif failed_count > 0:
            new_status = "Degraded"
        else:
            new_status = "Operational"
            
    if db_service.status != new_status:
        old_status = db_service.status
        db_service.status = new_status
        db.commit()
        db.refresh(db_service)
        logger.warning(f"Service '{db_service.name}' status changed from '{old_status}' to '{new_status}'")
    
    return db_service