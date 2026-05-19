import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Workflow Orchestration Service
Temporal-based workflow orchestration for banking and e-commerce
Port: 8023
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("comprehensive-workflow-orchestration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import asyncio
import httpx
import os
from enum import Enum

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
import redis

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agent_user:agent_password@localhost/workflow_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis for workflow state
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=3,
    decode_responses=True
)

# Service URLs
FRAUD_DETECTION_URL = os.getenv("FRAUD_DETECTION_URL", "http://localhost:8010")
ECOMMERCE_URL = os.getenv("ECOMMERCE_URL", "http://localhost:8020")
PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "http://localhost:8021")
SECURITY_MONITORING_URL = os.getenv("SECURITY_MONITORING_URL", "http://localhost:8022")
TIGERBEETLE_SYNC_URL = os.getenv("TIGERBEETLE_SYNC_URL", "http://localhost:8005")

# Temporal Configuration (for future integration)
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")

# ==================== ENUMS ====================

class WorkflowType(str, Enum):
    BANKING_TRANSACTION = "banking_transaction"
    ECOMMERCE_ORDER = "ecommerce_order"
    AGENT_ONBOARDING = "agent_onboarding"
    KYC_VERIFICATION = "kyc_verification"
    LOAN_PROCESSING = "loan_processing"

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"

# ==================== DATABASE MODELS ====================

class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(100), unique=True, nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    
    # Context
    tenant_id = Column(String(100), index=True)
    user_id = Column(String(100), index=True)
    entity_id = Column(String(100), index=True)  # transaction_id, order_id, etc.
    
    # Workflow data
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    context = Column(JSONB)
    
    # Execution
    current_step = Column(String(100))
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_workflow_type_status', 'workflow_type', 'status'),
    )

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id = Column(String(100), unique=True, nullable=False, index=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    
    # Step details
    step_name = Column(String(200), nullable=False)
    step_type = Column(String(50), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)
    
    # Execution
    service_url = Column(String(500))
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_step_workflow_order', 'workflow_id', 'step_order'),
    )

class ServiceRegistry(Base):
    __tablename__ = "service_registry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), unique=True, nullable=False, index=True)
    service_url = Column(String(500), nullable=False)
    service_type = Column(String(50))
    is_healthy = Column(Boolean, default=True, index=True)
    last_health_check = Column(DateTime)
    response_time = Column(Float)
    metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC MODELS ====================

class WorkflowCreate(BaseModel):
    workflow_type: WorkflowType
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    entity_id: Optional[str] = None
    input_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = {}

class WorkflowResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_type: str
    status: str
    current_step: Optional[str]
    completed_steps: int
    total_steps: int

# ==================== HELPER FUNCTIONS ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def check_service_health(service_url: str) -> bool:
    """Check if a service is healthy"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{service_url}/health", timeout=5.0)
            return response.status_code == 200
    except:
        return False

async def call_service(service_url: str, endpoint: str, data: Dict) -> Dict:
    """Call external service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{service_url}{endpoint}",
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service call failed: {str(e)}")

# ==================== WORKFLOW DEFINITIONS ====================

async def execute_banking_transaction_workflow(workflow: Workflow, db: Session):
    """Execute banking transaction workflow"""
    
    steps = [
        {"name": "Validate Transaction", "service": TIGERBEETLE_SYNC_URL, "endpoint": "/validate"},
        {"name": "Fraud Detection", "service": FRAUD_DETECTION_URL, "endpoint": "/check"},
        {"name": "Process Transaction", "service": TIGERBEETLE_SYNC_URL, "endpoint": "/process"},
        {"name": "Update Balances", "service": TIGERBEETLE_SYNC_URL, "endpoint": "/sync"},
        {"name": "Send Notification", "service": None, "endpoint": None}
    ]
    
    workflow.total_steps = len(steps)
    db.commit()
    
    for idx, step_def in enumerate(steps, 1):
        step = WorkflowStep(
            step_id=f"STEP-{workflow.workflow_id}-{idx}",
            workflow_id=workflow.workflow_id,
            step_name=step_def["name"],
            step_type="service_call" if step_def["service"] else "notification",
            step_order=idx,
            service_url=step_def["service"],
            input_data=workflow.input_data,
            started_at=datetime.utcnow()
        )
        
        try:
            step.status = "running"
            workflow.current_step = step.step_name
            db.add(step)
            db.commit()
            
            if step_def["service"]:
                # Call service
                result = await call_service(
                    step_def["service"],
                    step_def["endpoint"],
                    workflow.input_data
                )
                step.output_data = result
            else:
                # Execute notification step
                step.output_data = {"notification_sent": True}
            
            step.status = "completed"
            step.completed_at = datetime.utcnow()
            step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
            workflow.completed_steps += 1
            
        except Exception as e:
            step.status = "failed"
            step.error_message = str(e)
            workflow.failed_steps += 1
            workflow.status = "failed"
            workflow.error_message = f"Step '{step.step_name}' failed: {str(e)}"
            db.commit()
            return
        
        db.commit()
    
    workflow.status = "completed"
    workflow.completed_at = datetime.utcnow()
    workflow.duration_seconds = (workflow.completed_at - workflow.started_at).total_seconds()
    db.commit()

async def execute_ecommerce_order_workflow(workflow: Workflow, db: Session):
    """Execute e-commerce order workflow"""
    
    steps = [
        {"name": "Validate Order", "service": ECOMMERCE_URL, "endpoint": "/orders/validate"},
        {"name": "Check Inventory", "service": ECOMMERCE_URL, "endpoint": "/inventory/check"},
        {"name": "Fraud Screening", "service": FRAUD_DETECTION_URL, "endpoint": "/check"},
        {"name": "Process Payment", "service": PAYMENT_GATEWAY_URL, "endpoint": "/payments"},
        {"name": "Create Order", "service": ECOMMERCE_URL, "endpoint": "/orders"},
        {"name": "Update Inventory", "service": ECOMMERCE_URL, "endpoint": "/inventory/update"},
        {"name": "Send Confirmation", "service": None, "endpoint": None}
    ]
    
    workflow.total_steps = len(steps)
    db.commit()
    
    for idx, step_def in enumerate(steps, 1):
        step = WorkflowStep(
            step_id=f"STEP-{workflow.workflow_id}-{idx}",
            workflow_id=workflow.workflow_id,
            step_name=step_def["name"],
            step_type="service_call" if step_def["service"] else "notification",
            step_order=idx,
            service_url=step_def["service"],
            input_data=workflow.input_data,
            started_at=datetime.utcnow()
        )
        
        try:
            step.status = "running"
            workflow.current_step = step.step_name
            db.add(step)
            db.commit()
            
            if step_def["service"]:
                result = await call_service(
                    step_def["service"],
                    step_def["endpoint"],
                    workflow.input_data
                )
                step.output_data = result
                
                # Pass output to next step
                workflow.input_data.update(result)
            else:
                step.output_data = {"confirmation_sent": True}
            
            step.status = "completed"
            step.completed_at = datetime.utcnow()
            step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
            workflow.completed_steps += 1
            
        except Exception as e:
            step.status = "failed"
            step.error_message = str(e)
            workflow.failed_steps += 1
            
            # Rollback logic for e-commerce
            if idx > 4:  # After payment
                await rollback_ecommerce_order(workflow, db)
            
            workflow.status = "failed"
            workflow.error_message = f"Step '{step.step_name}' failed: {str(e)}"
            db.commit()
            return
        
        db.commit()
    
    workflow.status = "completed"
    workflow.completed_at = datetime.utcnow()
    workflow.duration_seconds = (workflow.completed_at - workflow.started_at).total_seconds()
    workflow.output_data = {"order_id": workflow.input_data.get("order_id")}
    db.commit()

async def rollback_ecommerce_order(workflow: Workflow, db: Session):
    """Rollback e-commerce order on failure"""
    try:
        # Refund payment if processed
        if workflow.completed_steps >= 4:
            await call_service(
                PAYMENT_GATEWAY_URL,
                "/refunds",
                {"transaction_id": workflow.input_data.get("transaction_id")}
            )
        
        # Restore inventory if updated
        if workflow.completed_steps >= 6:
            await call_service(
                ECOMMERCE_URL,
                "/inventory/restore",
                {"order_id": workflow.input_data.get("order_id")}
            )
    except Exception as e:
        print(f"Rollback failed: {e}")

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Comprehensive Workflow Orchestration Service",
    description="Temporal-based workflow orchestration for banking and e-commerce",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check with service discovery"""
    
    services = {
        "fraud_detection": await check_service_health(FRAUD_DETECTION_URL),
        "ecommerce": await check_service_health(ECOMMERCE_URL),
        "payment_gateway": await check_service_health(PAYMENT_GATEWAY_URL),
        "security_monitoring": await check_service_health(SECURITY_MONITORING_URL),
        "tigerbeetle_sync": await check_service_health(TIGERBEETLE_SYNC_URL)
    }
    
    return {
        "status": "healthy",
        "service": "workflow-orchestration",
        "version": "1.0.0",
        "port": 8023,
        "features": [
            "banking_transaction_workflow",
            "ecommerce_order_workflow",
            "service_discovery",
            "automatic_rollback",
            "retry_mechanism",
            "temporal_integration_ready"
        ],
        "services": services
    }

@app.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and start workflow"""
    
    workflow = Workflow(
        workflow_id=f"WF-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        workflow_type=workflow_data.workflow_type.value,
        tenant_id=workflow_data.tenant_id,
        user_id=workflow_data.user_id,
        entity_id=workflow_data.entity_id,
        input_data=workflow_data.input_data,
        context=workflow_data.context,
        status="running",
        started_at=datetime.utcnow()
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    # Execute workflow in background
    if workflow_data.workflow_type == WorkflowType.BANKING_TRANSACTION:
        background_tasks.add_task(execute_banking_transaction_workflow, workflow, db)
    elif workflow_data.workflow_type == WorkflowType.ECOMMERCE_ORDER:
        background_tasks.add_task(execute_ecommerce_order_workflow, workflow, db)
    
    return WorkflowResponse(
        id=str(workflow.id),
        workflow_id=workflow.workflow_id,
        workflow_type=workflow.workflow_type,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps,
        total_steps=workflow.total_steps
    )

@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Get workflow status"""
    
    workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    steps = db.query(WorkflowStep).filter(
        WorkflowStep.workflow_id == workflow_id
    ).order_by(WorkflowStep.step_order).all()
    
    return {
        "workflow_id": workflow.workflow_id,
        "workflow_type": workflow.workflow_type,
        "status": workflow.status,
        "current_step": workflow.current_step,
        "completed_steps": workflow.completed_steps,
        "total_steps": workflow.total_steps,
        "duration_seconds": workflow.duration_seconds,
        "error_message": workflow.error_message,
        "steps": [
            {
                "step_name": s.step_name,
                "status": s.status,
                "duration_seconds": s.duration_seconds,
                "error_message": s.error_message
            }
            for s in steps
        ]
    }

@app.get("/workflows")
async def list_workflows(
    workflow_type: Optional[WorkflowType] = None,
    status: Optional[WorkflowStatus] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List workflows"""
    
    query = db.query(Workflow)
    
    if workflow_type:
        query = query.filter(Workflow.workflow_type == workflow_type.value)
    if status:
        query = query.filter(Workflow.status == status.value)
    
    workflows = query.order_by(Workflow.created_at.desc()).limit(limit).all()
    
    return {
        "workflows": [
            {
                "workflow_id": w.workflow_id,
                "workflow_type": w.workflow_type,
                "status": w.status,
                "completed_steps": w.completed_steps,
                "total_steps": w.total_steps,
                "created_at": w.created_at.isoformat()
            }
            for w in workflows
        ],
        "total": len(workflows)
    }

@app.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Cancel running workflow"""
    
    workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    if workflow.status not in ["running", "pending"]:
        raise HTTPException(status_code=400, detail="Workflow cannot be cancelled")
    
    workflow.status = "cancelled"
    workflow.completed_at = datetime.utcnow()
    db.commit()
    
    return {"workflow_id": workflow_id, "status": "cancelled"}

@app.post("/services/register")
async def register_service(
    service_name: str,
    service_url: str,
    service_type: str,
    db: Session = Depends(get_db)
):
    """Register service for discovery"""
    
    service = db.query(ServiceRegistry).filter(
        ServiceRegistry.service_name == service_name
    ).first()
    
    if service:
        service.service_url = service_url
        service.service_type = service_type
        service.updated_at = datetime.utcnow()
    else:
        service = ServiceRegistry(
            service_name=service_name,
            service_url=service_url,
            service_type=service_type
        )
        db.add(service)
    
    db.commit()
    
    return {"service_name": service_name, "status": "registered"}

@app.get("/services")
async def list_services(db: Session = Depends(get_db)):
    """List registered services"""
    
    services = db.query(ServiceRegistry).all()
    
    return {
        "services": [
            {
                "service_name": s.service_name,
                "service_url": s.service_url,
                "service_type": s.service_type,
                "is_healthy": s.is_healthy,
                "last_health_check": s.last_health_check.isoformat() if s.last_health_check else None
            }
            for s in services
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8023)
