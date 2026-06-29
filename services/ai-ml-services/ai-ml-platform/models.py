import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base

# --- Utility Functions ---

def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()

# --- Core Models ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="owner")
    experiments: Mapped[List["Experiment"]] = relationship("Experiment", back_populates="owner")
    models: Mapped[List["Model"]] = relationship("Model", back_populates="owner")

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False) # e.g., S3 path, file system path
    version: Mapped[str] = mapped_column(String, default="1.0.0")
    row_count: Mapped[int] = mapped_column(Integer, nullable=True)
    file_size_mb: Mapped[float] = mapped_column(Float, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="datasets")
    experiments: Mapped[List["Experiment"]] = relationship("Experiment", back_populates="dataset")

    __table_args__ = (
        UniqueConstraint('name', 'version', name='_name_version_uc'),
    )

class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=True) # JSONB for flexible parameter storage
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=True) # JSONB for flexible metric storage
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="experiments")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="experiments")
    models: Mapped[List["Model"]] = relationship("Model", back_populates="experiment")

class Model(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String, default="1.0.0")
    framework: Mapped[str] = mapped_column(String, nullable=False) # e.g., 'PyTorch', 'TensorFlow', 'Scikit-learn'
    storage_path: Mapped[str] = mapped_column(String, nullable=False) # Path to the serialized model file
    performance_score: Mapped[float] = mapped_column(Float, nullable=True)
    is_production: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="models")
    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="models")

    __table_args__ = (
        UniqueConstraint('name', 'version', name='_model_name_version_uc'),
    )