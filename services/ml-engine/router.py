"""
Router for ml-engine service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ml-engine", tags=["ml-engine"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/metrics")
async def metrics_endpoint():
    return {"status": "ok"}

@router.post("/models/")
def create_ml_model(model: schemas.MLModelCreate, db: Session = Depends(get_db)):
    logger.info(f"Creating ML model: {model.name}")
    try:
        db_model = models.MLModel(**model.dict())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        logger.error(f"Error creating ML model: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@router.get("/models/")
def read_ml_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Reading ML models (skip={skip}, limit={limit}).")
    models_list = db.query(models.MLModel).offset(skip).limit(limit).all()
    return models_list

@router.get("/models/{model_id}")
def read_ml_model(model_id: int, db: Session = Depends(get_db)):
    logger.info(f"Reading ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    return db_model

@router.put("/models/{model_id}")
def update_ml_model(model_id: int, model: schemas.MLModelUpdate, db: Session = Depends(get_db)):
    logger.info(f"Updating ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found for update.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    try:
        for key, value in model.dict(exclude_unset=True).items():
            setattr(db_model, key, value)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        logger.error(f"Error updating ML model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@router.delete("/models/{model_id}")
def delete_ml_model(model_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found for deletion.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    try:
        db.delete(db_model)
        db.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error deleting ML model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

# Prediction Endpoints - protected by API key

@router.post("/predictions/")
def create_prediction(prediction: schemas.PredictionCreate, db: Session = Depends(get_db)):
    logger.info(f"Creating prediction for model ID: {prediction.model_id}")
    # In a real scenario, this would trigger an actual ML prediction
    # For now, we'll just store the request and a dummy result
    try:
        db_prediction = models.Prediction(
            model_id=prediction.model_id,
            request_data=prediction.request_data,
            prediction_result={"result": "pending_inference"}
        )
        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)
        return db_prediction
    except Exception as e:
        logger.error(f"Error creating prediction for model {prediction.model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@router.get("/predictions/")
def read_predictions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Reading predictions (skip={skip}, limit={limit}).")
    predictions_list = db.query(models.Prediction).offset(skip).limit(limit).all()
    return predictions_list

@router.get("/predictions/{prediction_id}")
def read_prediction(prediction_id: int, db: Session = Depends(get_db)):
    logger.info(f"Reading prediction with ID: {prediction_id}")
    db_prediction = db.query(models.Prediction).filter(models.Prediction.id == prediction_id).first()
    if db_prediction is None:
        logger.warning(f"Prediction with ID {prediction_id} not found.")
        raise HTTPException(status_code=404, detail="Prediction not found")
    return db_prediction

