import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, EmailStr

# --- Base Schemas ---

class BaseSchema(BaseModel):
    """Base schema for common configuration."""
    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }

# --- User Schemas ---

class UserBase(BaseSchema):
    username: str = Field(..., example="johndoe")
    email: EmailStr = Field(..., example="john.doe@example.com")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseSchema):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDBBase(UserBase):
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        # Exclude sensitive fields from the default response
        exclude = {'hashed_password'}

class User(UserInDBBase):
    # Relationships will be defined here for full response
    pass

# --- Dataset Schemas ---

class DatasetBase(BaseSchema):
    name: str = Field(..., example="iris_v1")
    description: Optional[str] = Field(None, example="The classic Iris dataset, version 1.")
    storage_path: str = Field(..., example="s3://ml-platform-data/iris/v1/data.csv")
    version: str = Field("1.0.0", example="1.0.0")
    row_count: Optional[int] = Field(None, example=150)
    file_size_mb: Optional[float] = Field(None, example=0.004)

class DatasetCreate(DatasetBase):
    pass

class DatasetUpdate(DatasetBase):
    name: Optional[str] = None
    storage_path: Optional[str] = None
    version: Optional[str] = None

class Dataset(DatasetBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # owner: Optional[User] # Optional: could lead to circular dependency if not careful

# --- Experiment Schemas ---

class ExperimentBase(BaseSchema):
    name: str = Field(..., example="logistic_regression_run_1")
    status: str = Field("PENDING", example="COMPLETED")
    parameters: Optional[Dict[str, Any]] = Field(None, example={"solver": "lbfgs", "C": 1.0})
    metrics: Optional[Dict[str, Any]] = Field(None, example={"accuracy": 0.98, "f1_score": 0.97})
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class ExperimentCreate(ExperimentBase):
    dataset_id: Optional[uuid.UUID] = Field(None, example="a1b2c3d4-e5f6-7890-1234-567890abcdef")

class ExperimentUpdate(ExperimentBase):
    name: Optional[str] = None
    status: Optional[str] = None
    dataset_id: Optional[uuid.UUID] = None

class Experiment(ExperimentBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    dataset_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    # dataset: Optional[Dataset] # Optional: avoid circular dependency

# --- Model Schemas ---

class ModelBase(BaseSchema):
    name: str = Field(..., example="iris_classifier")
    version: str = Field("1.0.0", example="1.0.0")
    framework: str = Field(..., example="Scikit-learn")
    storage_path: str = Field(..., example="s3://ml-platform-models/iris_classifier/v1/model.pkl")
    performance_score: Optional[float] = Field(None, example=0.98)
    is_production: bool = Field(False, example=True)

class ModelCreate(ModelBase):
    experiment_id: Optional[uuid.UUID] = Field(None, example="a1b2c3d4-e5f6-7890-1234-567890abcdef")

class ModelUpdate(ModelBase):
    name: Optional[str] = None
    version: Optional[str] = None
    framework: Optional[str] = None
    storage_path: Optional[str] = None
    is_production: Optional[bool] = None

class Model(ModelBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    experiment_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    # experiment: Optional[Experiment] # Optional: avoid circular dependency