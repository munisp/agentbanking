from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# --- Enums ---

class ExperimentStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"

# --- Model Schemas ---

class ModelBase(BaseModel):
    name: str = Field(..., description="The name of the AI model.")
    version: str = Field(..., description="The version of the AI model.")
    description: Optional[str] = Field(None, description="A brief description of the model.")
    framework: str = Field(..., description="The framework used (e.g., 'PyTorch', 'TensorFlow').")
    file_path: str = Field(..., description="The storage path or URI to the model file.")

class ModelCreate(ModelBase):
    pass

class ModelUpdate(ModelBase):
    name: Optional[str] = Field(None, description="The name of the AI model.")
    version: Optional[str] = Field(None, description="The version of the AI model.")
    framework: Optional[str] = Field(None, description="The framework used (e.g., 'PyTorch', 'TensorFlow').")
    file_path: Optional[str] = Field(None, description="The storage path or URI to the model file.")

class Model(ModelBase):
    id: int = Field(..., description="The unique identifier of the model.")
    created_at: datetime = Field(..., description="Timestamp of when the model was created.")
    updated_at: datetime = Field(..., description="Timestamp of the last update to the model.")

    model_config = ConfigDict(from_attributes=True)

# --- Experiment Schemas ---

class ExperimentBase(BaseModel):
    name: str = Field(..., description="The name of the experiment run.")
    description: Optional[str] = Field(None, description="A brief description of the experiment.")
    end_time: Optional[datetime] = Field(None, description="Timestamp of when the experiment ended.")
    status: ExperimentStatus = Field(ExperimentStatus.running, description="The current status of the experiment.")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics (e.g., {'accuracy': 0.95}).")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Hyperparameters used (e.g., {'learning_rate': 0.001}).")
    model_id: Optional[int] = Field(None, description="ID of the resulting model, if any.")

class ExperimentCreate(ExperimentBase):
    pass

class ExperimentUpdate(ExperimentBase):
    name: Optional[str] = Field(None, description="The name of the experiment run.")
    status: Optional[ExperimentStatus] = Field(None, description="The current status of the experiment.")

class Experiment(ExperimentBase):
    id: int = Field(..., description="The unique identifier of the experiment.")
    start_time: datetime = Field(..., description="Timestamp of when the experiment started.")
    created_at: datetime = Field(..., description="Timestamp of when the experiment record was created.")
    updated_at: datetime = Field(..., description="Timestamp of the last update to the experiment record.")

    model_config = ConfigDict(from_attributes=True)

# --- Response Schemas with Relationships (Optional, for completeness) ---

class ModelWithExperiments(Model):
    experiments: List["Experiment"] = []

class ExperimentWithModel(Experiment):
    model: Optional[Model] = None

# Update forward references
ModelWithExperiments.model_rebuild()
ExperimentWithModel.model_rebuild()
