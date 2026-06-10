"""
ETL/ELT Pipeline Service
Integrates all data sources into the lakehouse
Supports Agency Banking, E-commerce, Inventory, and Security domains
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import json
import httpx

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lakehouse ETL Pipeline",
    description="ETL/ELT pipelines for data integration",
    version="1.0.0"
)

# ============================================================================
# CONFIGURATION
# ============================================================================

LAKEHOUSE_URL = "http://localhost:8070"

# Source system endpoints
SOURCE_ENDPOINTS = {
    "agency_banking": "http://localhost:8000",
    "ecommerce": "http://localhost:8001",
    "inventory": "http://localhost:8002",
    "security": "http://localhost:8003"
}

# ============================================================================
# MODELS
# ============================================================================

class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class DataSource(str, Enum):
    AGENCY_BANKING = "agency_banking"
    ECOMMERCE = "ecommerce"
    INVENTORY = "inventory"
    SECURITY = "security"

class PipelineType(str, Enum):
    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"
    CDC = "cdc"  # Change Data Capture
    STREAMING = "streaming"

class PipelineConfig(BaseModel):
    pipeline_id: str
    name: str
    source: DataSource
    source_table: str
    target_domain: str
    target_layer: str
    target_table: str
    pipeline_type: PipelineType
    schedule: Optional[str] = None  # Cron expression
    enabled: bool = True
    transformations: List[str] = []

class PipelineRun(BaseModel):
    run_id: str
    pipeline_id: str
    status: PipelineStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    rows_extracted: int = 0
    rows_transformed: int = 0
    rows_loaded: int = 0
    error_message: Optional[str] = None

# ============================================================================
# ETL MANAGER
# ============================================================================

class ETLManager:
    """Manages ETL/ELT pipelines"""
    
    def __init__(self):
        self.pipelines: Dict[str, PipelineConfig] = {}
        self.runs: Dict[str, PipelineRun] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize default pipelines
        self._init_default_pipelines()
    
    def _init_default_pipelines(self):
        """Initialize default ETL pipelines for all domains"""
        
        # Agency Banking Pipelines
        self.register_pipeline(PipelineConfig(
            pipeline_id="ab_transactions_bronze",
            name="Agency Banking Transactions to Bronze",
            source=DataSource.AGENCY_BANKING,
            source_table="transactions",
            target_domain="agency_banking",
            target_layer="bronze",
            target_table="transactions_raw",
            pipeline_type=PipelineType.INCREMENTAL,
            schedule="*/15 * * * *",  # Every 15 minutes
            transformations=[]
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="ab_transactions_silver",
            name="Agency Banking Transactions to Silver",
            source=DataSource.AGENCY_BANKING,
            source_table="bronze.transactions_raw",
            target_domain="agency_banking",
            target_layer="silver",
            target_table="transactions_cleaned",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["clean_nulls", "validate_amounts", "enrich_location"]
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="ab_analytics_gold",
            name="Agency Banking Analytics to Gold",
            source=DataSource.AGENCY_BANKING,
            source_table="silver.transactions_cleaned",
            target_domain="agency_banking",
            target_layer="gold",
            target_table="daily_analytics",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["aggregate_daily", "calculate_metrics", "join_dimensions"]
        ))
        
        # E-commerce Pipelines
        self.register_pipeline(PipelineConfig(
            pipeline_id="ec_orders_bronze",
            name="E-commerce Orders to Bronze",
            source=DataSource.ECOMMERCE,
            source_table="orders",
            target_domain="ecommerce",
            target_layer="bronze",
            target_table="orders_raw",
            pipeline_type=PipelineType.INCREMENTAL,
            schedule="*/10 * * * *"  # Every 10 minutes
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="ec_orders_silver",
            name="E-commerce Orders to Silver",
            source=DataSource.ECOMMERCE,
            source_table="bronze.orders_raw",
            target_domain="ecommerce",
            target_layer="silver",
            target_table="orders_cleaned",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["clean_data", "validate_orders", "enrich_customer"]
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="ec_analytics_gold",
            name="E-commerce Analytics to Gold",
            source=DataSource.ECOMMERCE,
            source_table="silver.orders_cleaned",
            target_domain="ecommerce",
            target_layer="gold",
            target_table="sales_analytics",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["aggregate_sales", "calculate_revenue", "product_performance"]
        ))
        
        # Inventory Pipelines
        self.register_pipeline(PipelineConfig(
            pipeline_id="inv_stock_bronze",
            name="Inventory Stock to Bronze",
            source=DataSource.INVENTORY,
            source_table="stock_levels",
            target_domain="inventory",
            target_layer="bronze",
            target_table="stock_raw",
            pipeline_type=PipelineType.INCREMENTAL,
            schedule="*/5 * * * *"  # Every 5 minutes
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="inv_stock_silver",
            name="Inventory Stock to Silver",
            source=DataSource.INVENTORY,
            source_table="bronze.stock_raw",
            target_domain="inventory",
            target_layer="silver",
            target_table="stock_cleaned",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["validate_stock", "calculate_availability", "detect_anomalies"]
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="inv_analytics_gold",
            name="Inventory Analytics to Gold",
            source=DataSource.INVENTORY,
            source_table="silver.stock_cleaned",
            target_domain="inventory",
            target_layer="gold",
            target_table="inventory_analytics",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["aggregate_stock", "calculate_turnover", "predict_restock"]
        ))
        
        # Security Pipelines
        self.register_pipeline(PipelineConfig(
            pipeline_id="sec_events_bronze",
            name="Security Events to Bronze",
            source=DataSource.SECURITY,
            source_table="security_events",
            target_domain="security",
            target_layer="bronze",
            target_table="events_raw",
            pipeline_type=PipelineType.STREAMING,  # Real-time
            schedule="* * * * *"  # Every minute
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="sec_events_silver",
            name="Security Events to Silver",
            source=DataSource.SECURITY,
            source_table="bronze.events_raw",
            target_domain="security",
            target_layer="silver",
            target_table="events_classified",
            pipeline_type=PipelineType.STREAMING,
            transformations=["classify_threat", "enrich_context", "calculate_risk_score"]
        ))
        
        self.register_pipeline(PipelineConfig(
            pipeline_id="sec_analytics_gold",
            name="Security Analytics to Gold",
            source=DataSource.SECURITY,
            source_table="silver.events_classified",
            target_domain="security",
            target_layer="gold",
            target_table="threat_analytics",
            pipeline_type=PipelineType.INCREMENTAL,
            transformations=["aggregate_threats", "identify_patterns", "generate_alerts"]
        ))
        
        logger.info(f"Initialized {len(self.pipelines)} default pipelines")
    
    def register_pipeline(self, config: PipelineConfig):
        """Register a new pipeline"""
        self.pipelines[config.pipeline_id] = config
        logger.info(f"Registered pipeline: {config.pipeline_id}")
    
    async def run_pipeline(self, pipeline_id: str) -> PipelineRun:
        """Execute a pipeline"""
        if pipeline_id not in self.pipelines:
            raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
        
        config = self.pipelines[pipeline_id]
        
        # Create run record
        run = PipelineRun(
            run_id=f"{pipeline_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            pipeline_id=pipeline_id,
            status=PipelineStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        self.runs[run.run_id] = run
        
        try:
            # Extract
            logger.info(f"Extracting data from {config.source.value}.{config.source_table}")
            extracted_data = await self._extract(config)
            run.rows_extracted = len(extracted_data)
            
            # Transform
            logger.info(f"Transforming {len(extracted_data)} rows")
            transformed_data = await self._transform(extracted_data, config.transformations)
            run.rows_transformed = len(transformed_data)
            
            # Load
            logger.info(f"Loading {len(transformed_data)} rows to lakehouse")
            await self._load(transformed_data, config)
            run.rows_loaded = len(transformed_data)
            
            # Complete
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            
            logger.info(f"Pipeline {pipeline_id} completed successfully")
            
        except Exception as e:
            run.status = PipelineStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            logger.error(f"Pipeline {pipeline_id} failed: {e}")
        
        return run
    
    async def _extract(self, config: PipelineConfig) -> List[Dict[str, Any]]:
        """Extract data from source"""
        # Extract data from source
        # In production, this would call actual source APIs
        
        sample_data = {
            DataSource.AGENCY_BANKING: [
                {"transaction_id": f"TXN{i}", "amount": 1000 + i * 100, "agent_id": f"AG{i%10}", "timestamp": datetime.utcnow().isoformat()}
                for i in range(100)
            ],
            DataSource.ECOMMERCE: [
                {"order_id": f"ORD{i}", "total": 5000 + i * 50, "customer_id": f"CUST{i%20}", "status": "completed"}
                for i in range(100)
            ],
            DataSource.INVENTORY: [
                {"product_id": f"PROD{i}", "stock_level": 100 - i, "warehouse": f"WH{i%5}", "last_updated": datetime.utcnow().isoformat()}
                for i in range(100)
            ],
            DataSource.SECURITY: [
                {"event_id": f"EVT{i}", "event_type": "login_attempt", "user_id": f"USER{i%15}", "risk_score": i % 100}
                for i in range(100)
            ]
        }
        
        return sample_data.get(config.source, [])
    
    async def _transform(self, data: List[Dict[str, Any]], transformations: List[str]) -> List[Dict[str, Any]]:
        """Transform data"""
        transformed = data.copy()
        
        for transformation in transformations:
            if transformation == "clean_nulls":
                transformed = [row for row in transformed if all(v is not None for v in row.values())]
            elif transformation == "validate_amounts":
                transformed = [row for row in transformed if row.get("amount", 0) >= 0]
            elif transformation == "aggregate_daily":
                # Simplified aggregation
                pass
            # Add more transformations as needed
        
        return transformed
    
    async def _load(self, data: List[Dict[str, Any]], config: PipelineConfig):
        """Load data into lakehouse"""
        try:
            response = await self.http_client.post(
                f"{LAKEHOUSE_URL}/data/ingest",
                json={
                    "domain": config.target_domain,
                    "layer": config.target_layer,
                    "table_name": config.target_table,
                    "data": data,
                    "mode": "append" if config.pipeline_type == PipelineType.INCREMENTAL else "overwrite"
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to load data to lakehouse: {e}")
            raise
    
    async def run_all_pipelines(self):
        """Run all enabled pipelines"""
        results = []
        for pipeline_id, config in self.pipelines.items():
            if config.enabled:
                try:
                    run = await self.run_pipeline(pipeline_id)
                    results.append(run)
                except Exception as e:
                    logger.error(f"Failed to run pipeline {pipeline_id}: {e}")
        return results

# Global ETL manager
etl_manager = ETLManager()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "Lakehouse ETL Pipeline",
        "version": "1.0.0",
        "status": "operational",
        "pipelines": len(etl_manager.pipelines)
    }

@app.get("/pipelines")
async def list_pipelines():
    """List all pipelines"""
    return {
        "pipelines": [config.dict() for config in etl_manager.pipelines.values()],
        "total": len(etl_manager.pipelines)
    }

@app.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Get pipeline details"""
    if pipeline_id not in etl_manager.pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return etl_manager.pipelines[pipeline_id].dict()

@app.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, background_tasks: BackgroundTasks):
    """Run a specific pipeline"""
    run = await etl_manager.run_pipeline(pipeline_id)
    return run.dict()

@app.post("/pipelines/run-all")
async def run_all_pipelines(background_tasks: BackgroundTasks):
    """Run all enabled pipelines"""
    runs = await etl_manager.run_all_pipelines()
    return {
        "runs": [run.dict() for run in runs],
        "total": len(runs)
    }

@app.get("/runs")
async def list_runs():
    """List all pipeline runs"""
    return {
        "runs": [run.dict() for run in etl_manager.runs.values()],
        "total": len(etl_manager.runs)
    }

@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run details"""
    if run_id not in etl_manager.runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return etl_manager.runs[run_id].dict()

@app.get("/stats")
async def get_stats():
    """Get ETL statistics"""
    total_runs = len(etl_manager.runs)
    completed = sum(1 for run in etl_manager.runs.values() if run.status == PipelineStatus.COMPLETED)
    failed = sum(1 for run in etl_manager.runs.values() if run.status == PipelineStatus.FAILED)
    
    total_rows_loaded = sum(run.rows_loaded for run in etl_manager.runs.values())
    
    return {
        "total_pipelines": len(etl_manager.pipelines),
        "enabled_pipelines": sum(1 for p in etl_manager.pipelines.values() if p.enabled),
        "total_runs": total_runs,
        "completed_runs": completed,
        "failed_runs": failed,
        "success_rate": (completed / total_runs * 100) if total_runs > 0 else 0,
        "total_rows_loaded": total_rows_loaded
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8071)

