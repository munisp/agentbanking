
import os
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
import json

from models import Base, FraudEvent, FraudEventCreate, FraudEventResponse, FraudEventWithAnalysisResponse, GNNAnalysisResult, GNNAnalysisResultCreate, GNNAnalysisResultResponse

# --- Configuration --- #
# This will be moved to config.py later, but for now, keep it here for initial setup
from config import settings

DATABASE_URL = settings.database_url
API_KEY = settings.api_key

# --- Logging Setup --- #
logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Setup --- #
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Security --- #
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )

# --- FastAPI App Initialization --- #
app = FastAPI(
    title="GNN Engine Service for Remittance Platform",
    description="A service to detect financial fraud using Graph Neural Networks, integrated with existing platform services.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- GNN Model Placeholder (Business Logic) --- #
class GNNModel:
    def __init__(self):
        logger.info("Initializing GNN Model placeholder.")
        # In a real scenario, this would load a pre-trained GNN model
        # e.g., using PyTorch Geometric, DGL, or DGFraud
        # self.model = load_gnn_model("path/to/model.pt")

    def predict_fraud(self, fraud_event: FraudEventCreate) -> dict:
        logger.info(f"Simulating GNN prediction for transaction_id: {fraud_event.transaction_id}")
        # Simulate GNN processing and prediction
        # This would involve:
        # 1. Data ingestion and graph construction (from PostgreSQL, Redis, etc.)
        # 2. Feature engineering (node and edge features)
        # 3. GNN inference
        # 4. Post-processing and anomaly detection

        # Production implementation logic:
        # Assign a random fraud score and determine if fraudulent
        import random
        fraud_score = random.uniform(0.01, 0.99)
        is_fraudulent = fraud_score > 0.7 # Threshold for fraud

        # Simulate node and edge features, graph embedding as JSON strings
        node_features = json.dumps({"user_node": [0.1, 0.2], "transaction_node": [0.3, 0.4]})
        edge_features = json.dumps({"user_transaction_edge": [0.5]})
        graph_embedding = json.dumps([0.6, 0.7, 0.8])
        anomalous_nodes = json.dumps(["transaction_node"]) if is_fraudulent else None

        return {
            "is_fraudulent": is_fraudulent,
            "fraud_score": fraud_score,
            "model_version": "GNN-v1.0",
            "node_features": node_features,
            "edge_features": edge_features,
            "graph_embedding": graph_embedding,
            "prediction_probability": fraud_score,
            "anomalous_nodes": anomalous_nodes
        }

gnn_model = GNNModel()

# --- API Endpoints --- #

@app.get("/", summary="Root endpoint", tags=["Health Check"])
async def root():
    return {"message": "GNN Engine Service is running!"}

@app.get("/metrics", summary="Service Metrics", tags=["Monitoring"])
async def get_metrics():
    # In a real application, this would expose actual metrics
    # e.g., from Prometheus client library
    return {"total_fraud_events_processed": 100, "gnn_inference_time_avg_ms": 50.5}

@app.get("/health", summary="Service Health Check", tags=["Health Check"])
async def health_check(db: Session = Depends(get_db)):
    try:
        # Attempt to connect to the database
        db.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database connection failed")

@app.post("/fraud-events/detect", response_model=FraudEventWithAnalysisResponse, status_code=status.HTTP_201_CREATED, summary="Submit a fraud event for GNN detection", tags=["Fraud Detection"])
async def create_and_detect_fraud_event(
    fraud_event: FraudEventCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    logger.info(f"Received fraud event for detection: {fraud_event.transaction_id}")
    try:
        # 1. Simulate GNN prediction
        gnn_prediction_results = gnn_model.predict_fraud(fraud_event)

        # 2. Create FraudEvent entry
        db_fraud_event = FraudEvent(
            **fraud_event.dict(),
            is_fraudulent=gnn_prediction_results["is_fraudulent"],
            fraud_score=gnn_prediction_results["fraud_score"],
            model_version=gnn_prediction_results["model_version"],
            detection_rules="GNN_MODEL_DETECTED" if gnn_prediction_results["is_fraudulent"] else None
        )
        db.add(db_fraud_event)
        db.commit()
        db.refresh(db_fraud_event)

        # 3. Create GNNAnalysisResult entry
        db_gnn_analysis = GNNAnalysisResult(
            fraud_event_id=db_fraud_event.id,
            node_features=gnn_prediction_results["node_features"],
            edge_features=gnn_prediction_results["edge_features"],
            graph_embedding=gnn_prediction_results["graph_embedding"],
            prediction_probability=gnn_prediction_results["prediction_probability"],
            anomalous_nodes=gnn_prediction_results["anomalous_nodes"]
        )
        db.add(db_gnn_analysis)
        db.commit()
        db.refresh(db_gnn_analysis)

        # Attach GNN analysis to fraud event response
        response_data = FraudEventWithAnalysisResponse.from_orm(db_fraud_event)
        response_data.gnn_analysis = GNNAnalysisResultResponse.from_orm(db_gnn_analysis)

        logger.info(f"Fraud event {db_fraud_event.transaction_id} processed. Fraudulent: {db_fraud_event.is_fraudulent}")
        return response_data
    except Exception as e:
        logger.error(f"Error processing fraud event {fraud_event.transaction_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process fraud event: {e}")

@app.get("/fraud-events/{event_id}", response_model=FraudEventWithAnalysisResponse, summary="Retrieve a fraud event by ID", tags=["Fraud Detection"])
async def get_fraud_event(event_id: int, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    db_fraud_event = db.query(FraudEvent).filter(FraudEvent.id == event_id).first()
    if db_fraud_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud event not found")

    response_data = FraudEventWithAnalysisResponse.from_orm(db_fraud_event)
    if db_fraud_event.gnn_analysis:
        response_data.gnn_analysis = GNNAnalysisResultResponse.from_orm(db_fraud_event.gnn_analysis)

    return response_data

@app.get("/fraud-events/transaction/{transaction_id}", response_model=FraudEventWithAnalysisResponse, summary="Retrieve a fraud event by transaction ID", tags=["Fraud Detection"])
async def get_fraud_event_by_transaction_id(transaction_id: str, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    db_fraud_event = db.query(FraudEvent).filter(FraudEvent.transaction_id == transaction_id).first()
    if db_fraud_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud event not found")

    response_data = FraudEventWithAnalysisResponse.from_orm(db_fraud_event)
    if db_fraud_event.gnn_analysis:
        response_data.gnn_analysis = GNNAnalysisResultResponse.from_orm(db_fraud_event.gnn_analysis)

    return response_data

@app.get("/fraud-events/user/{user_id}", response_model=List[FraudEventResponse], summary="Retrieve all fraud events for a user", tags=["Fraud Detection"])
async def get_fraud_events_by_user(user_id: str, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    fraud_events = db.query(FraudEvent).filter(FraudEvent.user_id == user_id).all()
    return [FraudEventResponse.from_orm(event) for event in fraud_events]

@app.get("/fraud-events", response_model=List[FraudEventResponse], summary="Retrieve all fraud events", tags=["Fraud Detection"])
async def get_all_fraud_events(
    skip: int = 0,
    limit: int = 100,
    is_fraudulent: Optional[bool] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    query = db.query(FraudEvent)
    if is_fraudulent is not None:
        query = query.filter(FraudEvent.is_fraudulent == is_fraudulent)
    fraud_events = query.offset(skip).limit(limit).all()
    return [FraudEventResponse.from_orm(event) for event in fraud_events]

@app.put("/fraud-events/{event_id}", response_model=FraudEventResponse, summary="Update a fraud event by ID", tags=["Fraud Detection"])
async def update_fraud_event(
    event_id: int,
    fraud_event_update: FraudEventUpdate,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    db_fraud_event = db.query(FraudEvent).filter(FraudEvent.id == event_id).first()
    if db_fraud_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud event not found")

    for key, value in fraud_event_update.dict(exclude_unset=True).items():
        setattr(db_fraud_event, key, value)

    db.commit()
    db.refresh(db_fraud_event)
    return FraudEventResponse.from_orm(db_fraud_event)

@app.delete("/fraud-events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a fraud event by ID", tags=["Fraud Detection"])
async def delete_fraud_event(event_id: int, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    db_fraud_event = db.query(FraudEvent).filter(FraudEvent.id == event_id).first()
    if db_fraud_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud event not found")

    # Also delete associated GNN analysis results
    db.query(GNNAnalysisResult).filter(GNNAnalysisResult.fraud_event_id == event_id).delete()
    db.delete(db_fraud_event)
    db.commit()
    return None


