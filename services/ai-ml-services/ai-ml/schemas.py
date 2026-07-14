from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any

# --- Base Schemas ---

class MLProjectBase(BaseModel):
    name: str = Field(..., example="Customer Churn Prediction")
    description: Optional[str] = Field(None, example="Predicting which customers are likely to churn in the next quarter.")
    is_active: bool = Field(True, example=True)

class MLModelBase(BaseModel):
    name: str = Field(..., example="XGBoost Model V1")
    version: str = Field(..., example="1.0.0")
    model_path: str = Field(..., example="s3://ml-models/churn/v1/model.pkl")
    accuracy: Optional[float] = Field(None, example=0.925)
    is_current: bool = Field(False, example=False)

class PredictionBase(BaseModel):
    input_data: Any = Field(..., example={"feature_1": 10.5, "feature_2": "A"})
    output_data: Any = Field(..., example={"prediction": 0.15, "class": "No Churn"})

# --- Create Schemas (Input) ---

class MLProjectCreate(MLProjectBase):
    pass

class MLModelCreate(MLModelBase):
    project_id: int = Field(..., example=1)

class PredictionCreate(PredictionBase):
    project_id: int = Field(..., example=1)
    model_id: int = Field(..., example=1)

# --- Update Schemas (Input) ---

class MLProjectUpdate(MLProjectBase):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class MLModelUpdate(MLModelBase):
    name: Optional[str] = None
    version: Optional[str] = None
    model_path: Optional[str] = None
    accuracy: Optional[float] = None
    is_current: Optional[bool] = None

# --- Read Schemas (Output) ---

class MLProject(MLProjectBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class MLModel(MLModelBase):
    id: int
    project_id: int
    deployed_at: datetime

    class Config:
        from_attributes = True

class Prediction(PredictionBase):
    id: int
    project_id: int
    model_id: int
    predicted_at: datetime

    class Config:
        from_attributes = True

# --- Nested Schemas for Relationships ---

class MLProjectWithModels(MLProject):
    models: List[MLModel] = []

class MLModelWithProject(MLModel):
    project: MLProject

class PredictionWithDetails(Prediction):
    project: MLProject
    model: MLModel
