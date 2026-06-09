"""
Router for device-management service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/device-management", tags=["device-management"])

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return {"status": "ok"}

@router.post("/owners/")
def create_device_owner(owner: schemas.DeviceOwnerCreate, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} creating new device owner: {owner.name}")
    db_owner = models.DeviceOwner(name=owner.name, contact_person=owner.contact_person, contact_email=owner.contact_email)
    db.add(db_owner)
    db.commit()
    db.refresh(db_owner)
    DB_OPERATION_COUNT.labels(operation='create', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} created by {current_user}.")
    return db_owner

@router.get("/owners/")
def read_device_owners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} fetching device owners.")
    owners = db.query(models.DeviceOwner).offset(skip).limit(limit).all()
    DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='success').inc()
    return owners

@router.get("/owners/{owner_id}")
def read_device_owner(owner_id: int, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} fetching device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user}.")
        DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='success').inc()
    return db_owner

@router.put("/owners/{owner_id}")
def update_device_owner(owner_id: int, owner: schemas.DeviceOwnerUpdate, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} updating device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user} during update.")
        DB_OPERATION_COUNT.labels(operation='update', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    
    update_data = owner.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_owner, key, value)
    
    db.add(db_owner)
    db.commit()
    db.refresh(db_owner)
    DB_OPERATION_COUNT.labels(operation='update', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} updated by {current_user}.")
    return db_owner

@router.delete("/owners/{owner_id}")
def delete_device_owner(owner_id: int, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} deleting device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user} during deletion.")
        DB_OPERATION_COUNT.labels(operation='delete', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    db.delete(db_owner)
    db.commit()
    DB_OPERATION_COUNT.labels(operation='delete', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} deleted by {current_user}.")
    return {"message": "Device owner deleted successfully"}

# --- Device Endpoints ---

@router.post("/devices/")
def create_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} creating new device: {device.serial_number}")
    db_device = models.Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    DB_OPERATION_COUNT.labels(operation='create', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} created by {current_user}.")
    return db_device

@router.get("/devices/")
def read_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} fetching devices.")
    devices = db.query(models.Device).offset(skip).limit(limit).all()
    DB_OPERATION_COUNT.labels(operation='read', model='Device', status='success').inc()
    return devices

@router.get("/devices/{device_id}")
def read_device(device_id: int, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} fetching device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user}.")
        DB_OPERATION_COUNT.labels(operation='read', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    DB_OPERATION_COUNT.labels(operation='read', model='Device', status='success').inc()
    return db_device

@router.put("/devices/{device_id}")
def update_device(device_id: int, device: schemas.DeviceUpdate, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} updating device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user} during update.")
        DB_OPERATION_COUNT.labels(operation='update', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    update_data = device.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_device, key, value)
    
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    DB_OPERATION_COUNT.labels(operation='update', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} updated by {current_user}.")
    return db_device

@router.delete("/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    logger.info(f"User {current_user} deleting device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user} during deletion.")
        DB_OPERATION_COUNT.labels(operation='delete', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.delete(db_device)
    db.commit()
    DB_OPERATION_COUNT.labels(operation='delete', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} deleted by {current_user}.")
    return {"message": "Device deleted successfully"}

# Health check endpoint

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/metrics")
async def metrics():
    return {"status": "ok"}

