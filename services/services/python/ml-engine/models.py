from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(String, nullable=True)
    artifact_path = Column(String, nullable=False) # S3 path to model artifact
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    performance_metrics = Column(JSON, nullable=True) # Store metrics as JSON

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, nullable=False) # Foreign key to MLModel, simplified for now
    request_data = Column(JSON, nullable=False)
    prediction_result = Column(JSON, nullable=False)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="completed") # e.g., completed, failed, pending

