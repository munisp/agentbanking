import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    framework = Column(String, nullable=False) # e.g., 'PyTorch', 'TensorFlow', 'Scikit-learn'
    file_path = Column(String, nullable=False) # Path or URI to the stored model file
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    experiments = relationship("Experiment", back_populates="model")

    __table_args__ = (
        UniqueConstraint('name', 'version', name='_name_version_uc'),
    )

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(Enum("running", "completed", "failed", name="experiment_status"), default="running", nullable=False)
    metrics = Column(JSON, nullable=True) # Dictionary of performance metrics
    parameters = Column(JSON, nullable=True) # Dictionary of hyperparameters
    
    model_id = Column(Integer, ForeignKey("models.id"), nullable=True) # Optional: link to the resulting model
    model = relationship("Model", back_populates="experiments")

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
