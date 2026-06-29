import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Enhanced Workflow Orchestration Service
Temporal.io-based workflow orchestration with FastAPI REST API
Port: 8023
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("workflow-orchestration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import uvicorn
import os
import asyncio
import uuid

# Temporal imports
from temporalio.client import Client
from temporalio.worker import Worker

# Import workflows and activities
from workflows import WORKFLOW_REGISTRY, AgentOnboardingInput, TransactionInput, LoanApplicationInput, DisputeResolutionInput
from activities import ACTIVITIES

# Configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "remittance-workflows")

# Global Temporal client
temporal_client: Optional[Client] = None
worker_task: Optional[asyncio.Task] = None

# FastAPI app
app = FastAPI(
    title="Workflow Orchestration Service",
    description="Temporal.io-based workflow orchestration for 30 user journeys",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Models
# ============================================================================

class WorkflowStartRequest(BaseModel):
    """Request to start a workflow"""
    workflow_type: str
    workflow_id: Optional[str] = None
    input_data: Dict[str, Any]

class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    workflow_id: str
    workflow_type: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SignalRequest(BaseModel):
    """Request to send signal to workflow"""
    signal_name: str
    signal_data: Dict[str, Any]

# ============================================================================
# Temporal Client Management
# ============================================================================

async def get_temporal_client() -> Client:
    """Get or create Temporal client"""
    global temporal_client
    
    if temporal_client is None:
        temporal_client = await Client.connect(
            TEMPORAL_HOST,
            namespace=TEMPORAL_NAMESPACE
        )
    
    return temporal_client

async def start_temporal_worker():
    """Start Temporal worker"""
    client = await get_temporal_client()
    
    # Create worker
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=list(WORKFLOW_REGISTRY.values()),
        activities=ACTIVITIES
    )
    
    # Run worker
    await worker.run()

# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup event"""
    global worker_task
    
    # Start Temporal worker in background
    worker_task = asyncio.create_task(start_temporal_worker())
    
    print(f"✅ Workflow Orchestration Service started")
    print(f"✅ Temporal worker started on task queue: {TASK_QUEUE}")
    print(f"✅ {len(WORKFLOW_REGISTRY)} workflows registered")
    print(f"✅ {len(ACTIVITIES)} activities registered")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event"""
    global worker_task, temporal_client
    
    # Cancel worker task
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    
    # Close Temporal client
    if temporal_client:
        await temporal_client.close()
    
    print("✅ Workflow Orchestration Service stopped")

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "workflow-orchestration",
        "version": "2.0.0",
        "description": "Temporal.io-based workflow orchestration for 30 user journeys",
        "workflows_registered": len(WORKFLOW_REGISTRY),
        "activities_registered": len(ACTIVITIES),
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check"""
    try:
        client = await get_temporal_client()
        # Try to describe the namespace to check connection
        await client.describe_namespace()
        temporal_healthy = True
    except Exception as e:
        temporal_healthy = False
    
    return {
        "status": "healthy" if temporal_healthy else "degraded",
        "service": "workflow-orchestration",
        "temporal_connected": temporal_healthy,
        "workflows_registered": len(WORKFLOW_REGISTRY),
        "activities_registered": len(ACTIVITIES)
    }

@app.get("/api/v1/workflows")
async def list_workflows():
    """List available workflows"""
    workflows = []
    
    for workflow_type, workflow_class in WORKFLOW_REGISTRY.items():
        workflows.append({
            "workflow_type": workflow_type,
            "workflow_class": workflow_class.__name__,
            "description": workflow_class.__doc__ or "No description"
        })
    
    return {
        "total": len(workflows),
        "workflows": workflows
    }

@app.post("/api/v1/workflows/start", response_model=WorkflowStatusResponse)
async def start_workflow(request: WorkflowStartRequest):
    """Start a workflow"""
    
    # Validate workflow type
    if request.workflow_type not in WORKFLOW_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown workflow type: {request.workflow_type}. Available: {list(WORKFLOW_REGISTRY.keys())}"
        )
    
    # Generate workflow ID if not provided
    workflow_id = request.workflow_id or f"{request.workflow_type}-{uuid.uuid4()}"
    
    # Get workflow class
    workflow_class = WORKFLOW_REGISTRY[request.workflow_type]
    
    # Get Temporal client
    client = await get_temporal_client()
    
    try:
        # Start workflow
        handle = await client.start_workflow(
            workflow_class.run,
            request.input_data,
            id=workflow_id,
            task_queue=TASK_QUEUE
        )
        
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            workflow_type=request.workflow_type,
            status="running"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start workflow: {str(e)}"
        )

@app.get("/api/v1/workflows/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """Get workflow status"""
    
    client = await get_temporal_client()
    
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)
        
        # Try to get result (non-blocking)
        try:
            result = await asyncio.wait_for(handle.result(), timeout=0.1)
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                workflow_type="unknown",  # Would need to store this
                status="completed",
                result=result
            )
        except asyncio.TimeoutError:
            # Workflow still running
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                workflow_type="unknown",
                status="running"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {str(e)}"
        )

@app.post("/api/v1/workflows/{workflow_id}/signal")
async def send_workflow_signal(workflow_id: str, request: SignalRequest):
    """Send signal to workflow"""
    
    client = await get_temporal_client()
    
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)
        
        # Send signal
        await handle.signal(request.signal_name, request.signal_data)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "signal_name": request.signal_name
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send signal: {str(e)}"
        )

@app.post("/api/v1/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a workflow"""
    
    client = await get_temporal_client()
    
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)
        
        # Cancel workflow
        await handle.cancel()
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "cancelled"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel workflow: {str(e)}"
        )

@app.post("/api/v1/workflows/{workflow_id}/terminate")
async def terminate_workflow(workflow_id: str, reason: str = "User requested"):
    """Terminate a workflow"""
    
    client = await get_temporal_client()
    
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)
        
        # Terminate workflow
        await handle.terminate(reason)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "terminated",
            "reason": reason
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to terminate workflow: {str(e)}"
        )

# ============================================================================
# Convenience Endpoints for Specific Workflows
# ============================================================================

@app.post("/api/v1/workflows/agent-onboarding")
async def start_agent_onboarding(input_data: Dict[str, Any]):
    """Start agent onboarding workflow"""
    return await start_workflow(WorkflowStartRequest(
        workflow_type="agent_onboarding",
        input_data=input_data
    ))

@app.post("/api/v1/workflows/cash-in")
async def start_cash_in(input_data: Dict[str, Any]):
    """Start cash-in workflow"""
    return await start_workflow(WorkflowStartRequest(
        workflow_type="cash_in",
        input_data=input_data
    ))

@app.post("/api/v1/workflows/cash-out")
async def start_cash_out(input_data: Dict[str, Any]):
    """Start cash-out workflow"""
    return await start_workflow(WorkflowStartRequest(
        workflow_type="cash_out",
        input_data=input_data
    ))

@app.post("/api/v1/workflows/loan-application")
async def start_loan_application(input_data: Dict[str, Any]):
    """Start loan application workflow"""
    return await start_workflow(WorkflowStartRequest(
        workflow_type="loan_application",
        input_data=input_data
    ))

@app.post("/api/v1/workflows/dispute-resolution")
async def start_dispute_resolution(input_data: Dict[str, Any]):
    """Start dispute resolution workflow"""
    return await start_workflow(WorkflowStartRequest(
        workflow_type="dispute_resolution",
        input_data=input_data
    ))

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8023))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

