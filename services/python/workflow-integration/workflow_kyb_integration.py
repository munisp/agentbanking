import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Temporal KYB Workflow Integration Service
For agent hierarchy and business verification (open-source replacement)
Port: 8025
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("temporal-kyb-workflow-integration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import httpx
import os

from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agent_user:agent_password@localhost/workflow_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Temporal Configuration
TEMPORAL_API_URL = os.getenv("TEMPORAL_API_URL", "http://localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "kyb-verification")

# ==================== DATABASE MODELS ====================

class WorkflowVerification(Base):
    __tablename__ = "workflow_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id = Column(String(100), unique=True, nullable=False, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    business_name = Column(String(500))
    business_registration_number = Column(String(200))
    country = Column(String(2))
    
    # Temporal workflow
    temporal_workflow_id = Column(String(200), index=True)
    temporal_run_id = Column(String(200))
    
    # Verification status
    status = Column(String(50), default="pending", index=True)
    risk_level = Column(String(20))
    verification_result = Column(JSONB)
    
    # Documents verified
    documents_verified = Column(JSONB)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC MODELS ====================

class VerificationRequest(BaseModel):
    agent_id: str
    business_name: str
    business_registration_number: str
    country: str
    documents: Optional[List[Dict[str, Any]]] = []

# ==================== HELPER FUNCTIONS ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def create_temporal_workflow(data: Dict) -> Dict:
    """Create verification workflow via Temporal"""
    try:
        async with httpx.AsyncClient() as client:
            workflow_id = f"kyb-{data['business_registration_number']}-{uuid.uuid4().hex[:8]}"
            response = await client.post(
                f"{TEMPORAL_API_URL}/api/v1/namespaces/{TEMPORAL_NAMESPACE}/workflows",
                json={
                    "workflowId": workflow_id,
                    "workflowType": {"name": TEMPORAL_TASK_QUEUE},
                    "taskQueue": {"name": TEMPORAL_TASK_QUEUE},
                    "input": {
                        "payloads": [{
                            "data": {
                                "companyName": data["business_name"],
                                "registrationNumber": data["business_registration_number"],
                                "country": data["country"],
                                "documents": data.get("documents", [])
                            }
                        }]
                    }
                },
                timeout=30.0
            )
            if response.status_code in (200, 201):
                result = response.json()
                return {
                    "id": workflow_id,
                    "runId": result.get("runId", ""),
                    "status": "processing"
                }
            raise HTTPException(status_code=500, detail=f"Temporal returned {response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal workflow creation failed: {str(e)}")

async def get_temporal_workflow_status(workflow_id: str) -> Dict:
    """Get workflow status from Temporal"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TEMPORAL_API_URL}/api/v1/namespaces/{TEMPORAL_NAMESPACE}/workflows/{workflow_id}",
                timeout=10.0
            )
            if response.status_code == 200:
                result = response.json()
                status_map = {
                    "WORKFLOW_EXECUTION_STATUS_RUNNING": "processing",
                    "WORKFLOW_EXECUTION_STATUS_COMPLETED": "completed",
                    "WORKFLOW_EXECUTION_STATUS_FAILED": "failed",
                }
                raw_status = result.get("workflowExecutionInfo", {}).get("status", "")
                return {
                    "status": status_map.get(raw_status, "processing"),
                    "riskLevel": result.get("workflowExecutionInfo", {}).get("memo", {}).get("riskLevel", "medium")
                }
            return {"status": "processing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Temporal KYB Workflow Integration Service",
    description="Agent business verification via Temporal workflows (open-source)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "temporal-kyb-integration",
        "version": "2.0.0",
        "port": 8025,
        "temporal_configured": bool(TEMPORAL_API_URL),
        "features": [
            "kyb_verification",
            "document_verification",
            "risk_assessment",
            "agent_onboarding"
        ]
    }

@app.post("/verify")
async def create_verification(
    request: VerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create KYB verification for agent"""
    
    verification = WorkflowVerification(
        verification_id=f"VER-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        agent_id=request.agent_id,
        business_name=request.business_name,
        business_registration_number=request.business_registration_number,
        country=request.country,
        status="pending"
    )
    
    db.add(verification)
    db.commit()
    db.refresh(verification)
    
    try:
        workflow_data = await create_temporal_workflow({
            "business_name": request.business_name,
            "business_registration_number": request.business_registration_number,
            "country": request.country,
            "documents": request.documents
        })
        
        verification.temporal_workflow_id = workflow_data.get("id")
        verification.temporal_run_id = workflow_data.get("runId")
        verification.status = "processing"
        db.commit()
    except Exception as e:
        verification.status = "failed"
        db.commit()
        raise
    
    return {
        "verification_id": verification.verification_id,
        "status": verification.status,
        "workflow_id": verification.temporal_workflow_id
    }

@app.get("/verify/{verification_id}")
async def get_verification(verification_id: str, db: Session = Depends(get_db)):
    """Get verification status"""
    
    verification = db.query(WorkflowVerification).filter(
        WorkflowVerification.verification_id == verification_id
    ).first()
    
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    if verification.temporal_workflow_id:
        workflow_status = await get_temporal_workflow_status(verification.temporal_workflow_id)
        
        if workflow_status.get("status") == "completed":
            verification.status = "completed"
            verification.completed_at = datetime.utcnow()
            verification.verification_result = workflow_status
            verification.risk_level = workflow_status.get("riskLevel", "medium")
            db.commit()
    
    return {
        "verification_id": verification.verification_id,
        "agent_id": verification.agent_id,
        "business_name": verification.business_name,
        "status": verification.status,
        "risk_level": verification.risk_level,
        "verification_result": verification.verification_result,
        "started_at": verification.started_at.isoformat(),
        "completed_at": verification.completed_at.isoformat() if verification.completed_at else None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8025)
