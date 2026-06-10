from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class MLProject(Base):
    __tablename__ = "ml_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    models = relationship("MLModel", back_populates="project", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="project", cascade="all, delete-orphan")

class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("ml_projects.id"), nullable=False)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    model_path = Column(String, nullable=False) # Path to the serialized model file (e.g., S3 URL or local path)
    accuracy = Column(Float)
    is_current = Column(Boolean, default=False, nullable=False)
    deployed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("MLProject", back_populates="models")
    predictions = relationship("Prediction", back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        # Unique constraint on (project_id, name, version)
        # Note: The unique constraint on (project_id, name, version) is not explicitly defined here but is handled in the service layer's IntegrityError catch.
        # For production, a UniqueConstraint should be added to __table_args__.
    )

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("ml_projects.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False)
    input_data = Column(JSON, nullable=False) # JSON representation of the input features
    output_data = Column(JSON, nullable=False) # JSON representation of the prediction result
    predicted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    project = relationship("MLProject", back_populates="predictions")
    model = relationship("MLModel", back_populates="predictions")
