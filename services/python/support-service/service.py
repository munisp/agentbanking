"""
Business logic for support-service
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from . import models

class SupportserviceService:
    """Service class for support-service business logic."""
    
    @staticmethod
    def create(db: Session, data: dict):
        """Create new record."""
        obj = models.Supportservice(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    
    @staticmethod
    def get_by_id(db: Session, id: int):
        """Get record by ID."""
        return db.query(models.Supportservice).filter(
            models.Supportservice.id == id
        ).first()
    
    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100):
        """List all records."""
        return db.query(models.Supportservice).offset(skip).limit(limit).all()
    
    @staticmethod
    def update(db: Session, id: int, data: dict):
        """Update record."""
        obj = db.query(models.Supportservice).filter(
            models.Supportservice.id == id
        ).first()
        if obj:
            for key, value in data.items():
                setattr(obj, key, value)
            db.commit()
            db.refresh(obj)
        return obj
    
    @staticmethod
    def delete(db: Session, id: int):
        """Delete record."""
        obj = db.query(models.Supportservice).filter(
            models.Supportservice.id == id
        ).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj
