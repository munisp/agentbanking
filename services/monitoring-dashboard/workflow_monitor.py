"""
End-to-End Workflow Monitoring Dashboard
Tracks: Agent Onboarding → E-commerce → Supply Chain
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
import os
import uuid
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/remittance")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================================================================
# DATABASE MODELS
# ============================================================================

class WorkflowExecution(Base):
    """Track complete workflow executions"""
    __tablename__ = "workflow_executions"
    
    workflow_id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    store_id = Column(String, index=True)
    warehouse_id = Column(String, index=True)
    
    # Workflow metadata
    workflow_type = Column(String)  # "agent_onboarding", "order_fulfillment", etc.
    status = Column(String)  # "in_progress", "completed", "failed", "rolled_back"
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Stage tracking
    current_stage = Column(String)
    completed_stages = Column(JSON)  # List of completed stage names
    failed_stage = Column(String, nullable=True)
    
    # Metrics
    total_stages = Column(Integer)
    completed_stage_count = Column(Integer)
    progress_percentage = Column(Float)
    
    # Error tracking
    error_message = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Additional data
    metadata = Column(JSON)

class StageExecution(Base):
    """Track individual stage executions within workflows"""
    __tablename__ = "stage_executions"
    
    stage_id = Column(String, primary_key=True)
    workflow_id = Column(String, index=True)
    
    # Stage details
    stage_name = Column(String)
    stage_order = Column(Integer)
    stage_type = Column(String)  # "agent_registration", "store_creation", etc.
    
    # Status
    status = Column(String)  # "pending", "in_progress", "completed", "failed", "skipped"
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Data
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

class EventLog(Base):
    """Log all Fluvio events"""
    __tablename__ = "event_logs"
    
    event_id = Column(String, primary_key=True)
    topic = Column(String, index=True)
    event_type = Column(String, index=True)
    
    # References
    workflow_id = Column(String, index=True, nullable=True)
    agent_id = Column(String, index=True, nullable=True)
    store_id = Column(String, index=True, nullable=True)
    order_id = Column(String, index=True, nullable=True)
    
    # Event data
    event_data = Column(JSON)
    timestamp = Column(DateTime, index=True)
    
    # Processing
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)

# Create tables
Base.metadata.create_all(bind=engine)

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Workflow Monitoring Dashboard",
    description="Real-time monitoring of agent onboarding to e-commerce workflows",
    version="1.0.0"
)

# ============================================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# ============================================================================
# MONITORING SERVICE
# ============================================================================

class WorkflowMonitor:
    """Monitor and track workflow executions"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def start_workflow(
        self,
        workflow_id: str,
        workflow_type: str,
        agent_id: str,
        total_stages: int,
        metadata: Dict[str, Any]
    ) -> WorkflowExecution:
        """Start tracking a new workflow"""
        
        workflow = WorkflowExecution(
            workflow_id=workflow_id,
            agent_id=agent_id,
            workflow_type=workflow_type,
            status="in_progress",
            started_at=datetime.utcnow(),
            current_stage="initialization",
            completed_stages=[],
            total_stages=total_stages,
            completed_stage_count=0,
            progress_percentage=0.0,
            metadata=metadata
        )
        
        self.db.add(workflow)
        self.db.commit()
        
        logger.info(f"Started workflow: {workflow_id}")
        
        return workflow
    
    def start_stage(
        self,
        workflow_id: str,
        stage_name: str,
        stage_order: int,
        stage_type: str,
        input_data: Dict[str, Any]
    ) -> StageExecution:
        """Start tracking a stage execution"""
        
        stage_id = f"{workflow_id}-stage-{stage_order}"
        
        stage = StageExecution(
            stage_id=stage_id,
            workflow_id=workflow_id,
            stage_name=stage_name,
            stage_order=stage_order,
            stage_type=stage_type,
            status="in_progress",
            started_at=datetime.utcnow(),
            input_data=input_data,
            retry_count=0,
            max_retries=3
        )
        
        self.db.add(stage)
        
        # Update workflow current stage
        workflow = self.db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
        if workflow:
            workflow.current_stage = stage_name
        
        self.db.commit()
        
        logger.info(f"Started stage: {stage_name} for workflow {workflow_id}")
        
        return stage
    
    def complete_stage(
        self,
        workflow_id: str,
        stage_order: int,
        output_data: Dict[str, Any]
    ):
        """Mark stage as completed"""
        
        stage_id = f"{workflow_id}-stage-{stage_order}"
        stage = self.db.query(StageExecution).filter_by(stage_id=stage_id).first()
        
        if stage:
            stage.status = "completed"
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.output_data = output_data
            
            # Update workflow progress
            workflow = self.db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
            if workflow:
                workflow.completed_stages.append(stage.stage_name)
                workflow.completed_stage_count += 1
                workflow.progress_percentage = (workflow.completed_stage_count / workflow.total_stages) * 100
            
            self.db.commit()
            
            logger.info(f"Completed stage: {stage.stage_name}")
    
    def fail_stage(
        self,
        workflow_id: str,
        stage_order: int,
        error_message: str
    ):
        """Mark stage as failed"""
        
        stage_id = f"{workflow_id}-stage-{stage_order}"
        stage = self.db.query(StageExecution).filter_by(stage_id=stage_id).first()
        
        if stage:
            stage.status = "failed"
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.error_message = error_message
            
            # Update workflow
            workflow = self.db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
            if workflow:
                workflow.status = "failed"
                workflow.failed_stage = stage.stage_name
                workflow.error_message = error_message
            
            self.db.commit()
            
            logger.error(f"Failed stage: {stage.stage_name} - {error_message}")
    
    def complete_workflow(self, workflow_id: str):
        """Mark workflow as completed"""
        
        workflow = self.db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
        
        if workflow:
            workflow.status = "completed"
            workflow.completed_at = datetime.utcnow()
            workflow.duration_seconds = (workflow.completed_at - workflow.started_at).total_seconds()
            workflow.progress_percentage = 100.0
            
            self.db.commit()
            
            logger.info(f"Completed workflow: {workflow_id}")
    
    def log_event(
        self,
        topic: str,
        event_type: str,
        event_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        store_id: Optional[str] = None,
        order_id: Optional[str] = None
    ):
        """Log Fluvio event"""
        
        event = EventLog(
            event_id=str(uuid.uuid4()),
            topic=topic,
            event_type=event_type,
            workflow_id=workflow_id,
            agent_id=agent_id,
            store_id=store_id,
            order_id=order_id,
            event_data=event_data,
            timestamp=datetime.utcnow(),
            processed=False
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.info(f"Logged event: {event_type} on topic {topic}")
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get complete workflow status"""
        
        workflow = self.db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
        
        if not workflow:
            return None
        
        stages = self.db.query(StageExecution).filter_by(workflow_id=workflow_id).order_by(StageExecution.stage_order).all()
        
        return {
            "workflow_id": workflow.workflow_id,
            "agent_id": workflow.agent_id,
            "store_id": workflow.store_id,
            "warehouse_id": workflow.warehouse_id,
            "workflow_type": workflow.workflow_type,
            "status": workflow.status,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "duration_seconds": workflow.duration_seconds,
            "current_stage": workflow.current_stage,
            "progress_percentage": workflow.progress_percentage,
            "total_stages": workflow.total_stages,
            "completed_stage_count": workflow.completed_stage_count,
            "error_message": workflow.error_message,
            "stages": [
                {
                    "stage_name": stage.stage_name,
                    "stage_order": stage.stage_order,
                    "status": stage.status,
                    "started_at": stage.started_at.isoformat() if stage.started_at else None,
                    "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                    "duration_seconds": stage.duration_seconds,
                    "error_message": stage.error_message
                }
                for stage in stages
            ]
        }
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get dashboard metrics"""
        
        # Total workflows
        total_workflows = self.db.query(WorkflowExecution).count()
        
        # Workflows by status
        in_progress = self.db.query(WorkflowExecution).filter_by(status="in_progress").count()
        completed = self.db.query(WorkflowExecution).filter_by(status="completed").count()
        failed = self.db.query(WorkflowExecution).filter_by(status="failed").count()
        
        # Recent workflows
        recent_workflows = self.db.query(WorkflowExecution).order_by(
            WorkflowExecution.started_at.desc()
        ).limit(10).all()
        
        # Average duration
        completed_workflows = self.db.query(WorkflowExecution).filter_by(status="completed").all()
        avg_duration = sum(w.duration_seconds for w in completed_workflows if w.duration_seconds) / len(completed_workflows) if completed_workflows else 0
        
        # Success rate
        total_finished = completed + failed
        success_rate = (completed / total_finished * 100) if total_finished > 0 else 0
        
        # Events in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_events = self.db.query(EventLog).filter(
            EventLog.timestamp >= one_hour_ago
        ).count()
        
        return {
            "total_workflows": total_workflows,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration, 2),
            "recent_events_count": recent_events,
            "recent_workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "agent_id": w.agent_id,
                    "workflow_type": w.workflow_type,
                    "status": w.status,
                    "progress_percentage": w.progress_percentage,
                    "started_at": w.started_at.isoformat() if w.started_at else None
                }
                for w in recent_workflows
            ]
        }

monitor = WorkflowMonitor()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve monitoring dashboard HTML"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Workflow Monitoring Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #0f172a;
                color: #e2e8f0;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            .header h1 {
                font-size: 32px;
                margin-bottom: 10px;
            }
            .header p {
                opacity: 0.9;
                font-size: 16px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .metric-card {
                background: #1e293b;
                padding: 25px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .metric-card h3 {
                font-size: 14px;
                color: #94a3b8;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .metric-card .value {
                font-size: 36px;
                font-weight: bold;
                color: #667eea;
            }
            .metric-card .label {
                font-size: 12px;
                color: #64748b;
                margin-top: 5px;
            }
            .workflows-section {
                background: #1e293b;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .workflows-section h2 {
                margin-bottom: 20px;
                color: #e2e8f0;
            }
            .workflow-item {
                background: #0f172a;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 15px;
                border-left: 4px solid #10b981;
            }
            .workflow-item.in-progress {
                border-left-color: #f59e0b;
            }
            .workflow-item.failed {
                border-left-color: #ef4444;
            }
            .workflow-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .workflow-id {
                font-weight: bold;
                color: #667eea;
            }
            .status-badge {
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }
            .status-badge.completed {
                background: #10b981;
                color: white;
            }
            .status-badge.in-progress {
                background: #f59e0b;
                color: white;
            }
            .status-badge.failed {
                background: #ef4444;
                color: white;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #0f172a;
                border-radius: 10px;
                overflow: hidden;
                margin-top: 10px;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                transition: width 0.3s ease;
            }
            .realtime-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                background: #10b981;
                border-radius: 50%;
                margin-right: 10px;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1><span class="realtime-indicator"></span>Workflow Monitoring Dashboard</h1>
            <p>Real-time tracking of Agent Onboarding → E-commerce → Supply Chain</p>
        </div>
        
        <div class="metrics-grid" id="metrics">
            <!-- Metrics will be loaded here -->
        </div>
        
        <div class="workflows-section">
            <h2>Recent Workflows</h2>
            <div id="workflows">
                <!-- Workflows will be loaded here -->
            </div>
        </div>
        
        <script>
            const ws = new WebSocket('ws://localhost:8030/ws');
            
            ws.onopen = () => {
                console.log('Connected to monitoring dashboard');
                loadMetrics();
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                console.log('Received update:', data);
                loadMetrics();
            };
            
            async function loadMetrics() {
                const response = await fetch('/metrics');
                const data = await response.json();
                
                document.getElementById('metrics').innerHTML = `
                    <div class="metric-card">
                        <h3>Total Workflows</h3>
                        <div class="value">${data.total_workflows}</div>
                        <div class="label">All time</div>
                    </div>
                    <div class="metric-card">
                        <h3>In Progress</h3>
                        <div class="value">${data.in_progress}</div>
                        <div class="label">Currently running</div>
                    </div>
                    <div class="metric-card">
                        <h3>Success Rate</h3>
                        <div class="value">${data.success_rate}%</div>
                        <div class="label">${data.completed} completed, ${data.failed} failed</div>
                    </div>
                    <div class="metric-card">
                        <h3>Avg Duration</h3>
                        <div class="value">${Math.round(data.avg_duration_seconds)}s</div>
                        <div class="label">Per workflow</div>
                    </div>
                `;
                
                document.getElementById('workflows').innerHTML = data.recent_workflows.map(w => `
                    <div class="workflow-item ${w.status}">
                        <div class="workflow-header">
                            <span class="workflow-id">${w.workflow_id}</span>
                            <span class="status-badge ${w.status}">${w.status}</span>
                        </div>
                        <div>Agent: ${w.agent_id}</div>
                        <div>Type: ${w.workflow_type}</div>
                        <div>Started: ${new Date(w.started_at).toLocaleString()}</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${w.progress_percentage}%"></div>
                        </div>
                    </div>
                `).join('');
            }
            
            // Refresh every 5 seconds
            setInterval(loadMetrics, 5000);
        </script>
    </body>
    </html>
    """

@app.get("/metrics")
async def get_metrics():
    """Get dashboard metrics"""
    return monitor.get_dashboard_metrics()

@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow status"""
    return monitor.get_workflow_status(workflow_id)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "service": "workflow-monitor"}

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def broadcast_updates():
    """Broadcast metrics updates to all connected clients"""
    while True:
        try:
            metrics = monitor.get_dashboard_metrics()
            await manager.broadcast({
                "type": "metrics_update",
                "data": metrics
            })
        except Exception as e:
            logger.error(f"Error broadcasting updates: {e}")
        
        await asyncio.sleep(5)  # Broadcast every 5 seconds

@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(broadcast_updates())

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)

