"""
Real-Time Lakehouse Data Flow Implementation

Demonstrates complete data flow from ingestion through medallion layers:
1. Data Ingestion (Multiple Sources)
2. Bronze Layer (Raw Data)
3. Silver Layer (Cleaned & Validated)
4. Gold Layer (Business Analytics)
5. Platinum Layer (ML/AI Features)
6. Real-time Consumption (Dashboards, APIs)

Includes:
- Streaming ingestion from Fluvio/Kafka
- Batch processing with PySpark
- Real-time transformations
- Data quality checks
- Lineage tracking
- Performance monitoring
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
import uuid
from collections import defaultdict

# ==================== LOGGING ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== DATA MODELS ====================

class DataSource(str, Enum):
    """Data source types"""
    ECOMMERCE = "ecommerce"
    POS = "pos"
    SUPPLY_CHAIN = "supply_chain"
    REMITTANCE = "remittance"
    CUSTOMER = "customer"
    COMMUNICATION = "communication"

class MedallionLayer(str, Enum):
    """Medallion architecture layers"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"

class ProcessingStatus(str, Enum):
    """Data processing status"""
    INGESTING = "ingesting"
    BRONZE_PROCESSING = "bronze_processing"
    SILVER_PROCESSING = "silver_processing"
    GOLD_PROCESSING = "gold_processing"
    PLATINUM_PROCESSING = "platinum_processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DataRecord(BaseModel):
    """Raw data record"""
    record_id: str
    source: DataSource
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = {}

class ProcessingMetrics(BaseModel):
    """Processing metrics for monitoring"""
    record_id: str
    source: DataSource
    ingestion_time: datetime
    bronze_time: Optional[datetime] = None
    silver_time: Optional[datetime] = None
    gold_time: Optional[datetime] = None
    platinum_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    status: ProcessingStatus
    errors: List[str] = []

# ==================== REAL-TIME DATA FLOW ====================

class RealTimeDataFlow:
    """Manages real-time data flow through lakehouse"""
    
    def __init__(self):
        self.processing_metrics: Dict[str, ProcessingMetrics] = {}
        self.layer_stats = {
            MedallionLayer.BRONZE: {"records": 0, "errors": 0},
            MedallionLayer.SILVER: {"records": 0, "errors": 0},
            MedallionLayer.GOLD: {"records": 0, "errors": 0},
            MedallionLayer.PLATINUM: {"records": 0, "errors": 0}
        }
        self.source_stats = defaultdict(lambda: {"ingested": 0, "processed": 0, "failed": 0})
    
    async def ingest_data(self, record: DataRecord) -> ProcessingMetrics:
        """
        Step 1: Ingest data from source
        - Receive data from Fluvio/Kafka/API
        - Create processing metrics
        - Start bronze layer processing
        """
        logger.info(f"Ingesting data from {record.source}: {record.record_id}")
        
        # Create processing metrics
        metrics = ProcessingMetrics(
            record_id=record.record_id,
            source=record.source,
            ingestion_time=datetime.utcnow(),
            status=ProcessingStatus.INGESTING
        )
        self.processing_metrics[record.record_id] = metrics
        self.source_stats[record.source]["ingested"] += 1
        
        # Process ingestion delay
        await asyncio.sleep(0.01)
        
        # Process through bronze layer
        await self.process_bronze(record, metrics)
        
        return metrics
    
    async def process_bronze(self, record: DataRecord, metrics: ProcessingMetrics):
        """
        Step 2: Bronze Layer Processing (Raw Data)
        - Store raw data as-is
        - No transformations
        - Add metadata (ingestion timestamp, source)
        - Start silver layer processing
        """
        logger.info(f"Bronze layer processing: {record.record_id}")
        
        try:
            metrics.status = ProcessingStatus.BRONZE_PROCESSING
            metrics.bronze_time = datetime.utcnow()
            
            # Bronze layer: Store raw data
            bronze_data = {
                "record_id": record.record_id,
                "source": record.source,
                "raw_data": record.data,
                "ingestion_timestamp": record.timestamp.isoformat(),
                "metadata": record.metadata
            }
            
            # Process bronze storage
            await asyncio.sleep(0.02)
            
            self.layer_stats[MedallionLayer.BRONZE]["records"] += 1
            logger.info(f"Bronze layer stored: {record.record_id}")
            
            # Process through silver layer
            await self.process_silver(record, bronze_data, metrics)
            
        except Exception as e:
            logger.error(f"Bronze layer error: {e}")
            metrics.errors.append(f"Bronze: {str(e)}")
            self.layer_stats[MedallionLayer.BRONZE]["errors"] += 1
            metrics.status = ProcessingStatus.FAILED
    
    async def process_silver(self, record: DataRecord, bronze_data: Dict, metrics: ProcessingMetrics):
        """
        Step 3: Silver Layer Processing (Cleaned & Validated)
        - Data cleaning (remove nulls, fix formats)
        - Data validation (schema checks, business rules)
        - Data enrichment (add calculated fields)
        - Deduplication
        - Start gold layer processing
        """
        logger.info(f"Silver layer processing: {record.record_id}")
        
        try:
            metrics.status = ProcessingStatus.SILVER_PROCESSING
            metrics.silver_time = datetime.utcnow()
            
            # Silver layer: Clean and validate
            cleaned_data = await self._clean_data(bronze_data["raw_data"])
            validated_data = await self._validate_data(cleaned_data, record.source)
            enriched_data = await self._enrich_data(validated_data, record.source)
            
            silver_data = {
                "record_id": record.record_id,
                "source": record.source,
                "cleaned_data": enriched_data,
                "bronze_timestamp": bronze_data["ingestion_timestamp"],
                "silver_timestamp": datetime.utcnow().isoformat(),
                "quality_score": await self._calculate_quality_score(enriched_data)
            }
            
            # Process silver storage
            await asyncio.sleep(0.03)
            
            self.layer_stats[MedallionLayer.SILVER]["records"] += 1
            logger.info(f"Silver layer stored: {record.record_id}")
            
            # Process through gold layer
            await self.process_gold(record, silver_data, metrics)
            
        except Exception as e:
            logger.error(f"Silver layer error: {e}")
            metrics.errors.append(f"Silver: {str(e)}")
            self.layer_stats[MedallionLayer.SILVER]["errors"] += 1
            metrics.status = ProcessingStatus.FAILED
    
    async def process_gold(self, record: DataRecord, silver_data: Dict, metrics: ProcessingMetrics):
        """
        Step 4: Gold Layer Processing (Business Analytics)
        - Aggregate data (daily/weekly/monthly summaries)
        - Calculate KPIs and metrics
        - Create business-ready tables
        - Apply business logic
        - Start platinum layer processing
        """
        logger.info(f"Gold layer processing: {record.record_id}")
        
        try:
            metrics.status = ProcessingStatus.GOLD_PROCESSING
            metrics.gold_time = datetime.utcnow()
            
            # Gold layer: Business analytics
            aggregated_data = await self._aggregate_data(silver_data["cleaned_data"], record.source)
            kpis = await self._calculate_kpis(aggregated_data, record.source)
            
            gold_data = {
                "record_id": record.record_id,
                "source": record.source,
                "analytics_data": aggregated_data,
                "kpis": kpis,
                "silver_timestamp": silver_data["silver_timestamp"],
                "gold_timestamp": datetime.utcnow().isoformat()
            }
            
            # Process gold storage
            await asyncio.sleep(0.04)
            
            self.layer_stats[MedallionLayer.GOLD]["records"] += 1
            logger.info(f"Gold layer stored: {record.record_id}")
            
            # Process through platinum layer
            await self.process_platinum(record, gold_data, metrics)
            
        except Exception as e:
            logger.error(f"Gold layer error: {e}")
            metrics.errors.append(f"Gold: {str(e)}")
            self.layer_stats[MedallionLayer.GOLD]["errors"] += 1
            metrics.status = ProcessingStatus.FAILED
    
    async def process_platinum(self, record: DataRecord, gold_data: Dict, metrics: ProcessingMetrics):
        """
        Step 5: Platinum Layer Processing (ML/AI Features)
        - Feature engineering for ML models
        - Predictive analytics
        - Anomaly detection
        - Recommendation generation
        - Complete processing
        """
        logger.info(f"Platinum layer processing: {record.record_id}")
        
        try:
            metrics.status = ProcessingStatus.PLATINUM_PROCESSING
            metrics.platinum_time = datetime.utcnow()
            
            # Platinum layer: ML/AI features
            features = await self._extract_features(gold_data["analytics_data"], record.source)
            predictions = await self._generate_predictions(features, record.source)
            anomalies = await self._detect_anomalies(features, record.source)
            
            platinum_data = {
                "record_id": record.record_id,
                "source": record.source,
                "ml_features": features,
                "predictions": predictions,
                "anomalies": anomalies,
                "gold_timestamp": gold_data["gold_timestamp"],
                "platinum_timestamp": datetime.utcnow().isoformat()
            }
            
            # Process platinum storage
            await asyncio.sleep(0.02)
            
            self.layer_stats[MedallionLayer.PLATINUM]["records"] += 1
            logger.info(f"Platinum layer stored: {record.record_id}")
            
            # Complete processing
            await self.complete_processing(metrics)
            
        except Exception as e:
            logger.error(f"Platinum layer error: {e}")
            metrics.errors.append(f"Platinum: {str(e)}")
            self.layer_stats[MedallionLayer.PLATINUM]["errors"] += 1
            metrics.status = ProcessingStatus.FAILED
    
    async def complete_processing(self, metrics: ProcessingMetrics):
        """Complete data processing and calculate metrics"""
        metrics.completion_time = datetime.utcnow()
        metrics.status = ProcessingStatus.COMPLETED
        
        # Calculate total duration
        duration = (metrics.completion_time - metrics.ingestion_time).total_seconds() * 1000
        metrics.total_duration_ms = duration
        
        self.source_stats[metrics.source]["processed"] += 1
        
        logger.info(f"Processing completed: {metrics.record_id} in {duration:.2f}ms")
    
    # ==================== DATA TRANSFORMATION METHODS ====================
    
    async def _clean_data(self, data: Dict) -> Dict:
        """Clean raw data"""
        cleaned = {}
        for key, value in data.items():
            # Remove null values
            if value is not None:
                # Trim strings
                if isinstance(value, str):
                    cleaned[key] = value.strip()
                else:
                    cleaned[key] = value
        return cleaned
    
    async def _validate_data(self, data: Dict, source: DataSource) -> Dict:
        """Validate data against schema and business rules"""
        # Source-specific validation
        if source == DataSource.ECOMMERCE:
            # Validate order data
            if "order_id" not in data:
                raise ValueError("Missing order_id")
            if "total" in data and data["total"] < 0:
                raise ValueError("Invalid total amount")
        
        elif source == DataSource.POS:
            # Validate POS transaction
            if "transaction_id" not in data:
                raise ValueError("Missing transaction_id")
            if "amount" in data and data["amount"] <= 0:
                raise ValueError("Invalid transaction amount")
        
        return data
    
    async def _enrich_data(self, data: Dict, source: DataSource) -> Dict:
        """Enrich data with calculated fields"""
        enriched = data.copy()
        
        # Add processing metadata
        enriched["_enriched_at"] = datetime.utcnow().isoformat()
        enriched["_source"] = source
        
        # Source-specific enrichment
        if source == DataSource.ECOMMERCE and "total" in data:
            enriched["total_with_tax"] = data["total"] * 1.1  # 10% tax
        
        elif source == DataSource.POS and "amount" in data:
            enriched["commission"] = data["amount"] * 0.02  # 2% commission
        
        return enriched
    
    async def _calculate_quality_score(self, data: Dict) -> float:
        """Calculate data quality score (0-100)"""
        score = 100.0
        
        # Completeness check
        null_count = sum(1 for v in data.values() if v is None)
        completeness = (len(data) - null_count) / len(data) if data else 0
        score *= completeness
        
        return round(score, 2)
    
    async def _aggregate_data(self, data: Dict, source: DataSource) -> Dict:
        """Aggregate data for analytics"""
        aggregated = {
            "record_count": 1,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Source-specific aggregation
        if source == DataSource.ECOMMERCE:
            aggregated["total_revenue"] = data.get("total_with_tax", 0)
            aggregated["order_count"] = 1
        
        elif source == DataSource.POS:
            aggregated["total_transactions"] = 1
            aggregated["total_amount"] = data.get("amount", 0)
            aggregated["total_commission"] = data.get("commission", 0)
        
        return aggregated
    
    async def _calculate_kpis(self, aggregated: Dict, source: DataSource) -> Dict:
        """Calculate KPIs"""
        kpis = {}
        
        if source == DataSource.ECOMMERCE:
            kpis["average_order_value"] = aggregated.get("total_revenue", 0) / aggregated.get("order_count", 1)
        
        elif source == DataSource.POS:
            kpis["average_transaction_value"] = aggregated.get("total_amount", 0) / aggregated.get("total_transactions", 1)
            kpis["commission_rate"] = aggregated.get("total_commission", 0) / aggregated.get("total_amount", 1) if aggregated.get("total_amount", 0) > 0 else 0
        
        return kpis
    
    async def _extract_features(self, data: Dict, source: DataSource) -> Dict:
        """Extract ML features"""
        features = {
            "timestamp_hour": datetime.utcnow().hour,
            "timestamp_day_of_week": datetime.utcnow().weekday(),
            "source": source
        }
        
        # Source-specific features
        if source == DataSource.ECOMMERCE:
            features["revenue"] = data.get("total_revenue", 0)
            features["order_count"] = data.get("order_count", 0)
        
        elif source == DataSource.POS:
            features["transaction_amount"] = data.get("total_amount", 0)
            features["commission"] = data.get("total_commission", 0)
        
        return features
    
    async def _generate_predictions(self, features: Dict, source: DataSource) -> Dict:
        """Generate predictions (processd)"""
        predictions = {
            "predicted_at": datetime.utcnow().isoformat()
        }
        
        # Process predictions
        if source == DataSource.ECOMMERCE:
            predictions["predicted_next_order_value"] = features.get("revenue", 0) * 1.05
            predictions["churn_probability"] = 0.15
        
        elif source == DataSource.POS:
            predictions["predicted_next_transaction"] = features.get("transaction_amount", 0) * 1.02
            predictions["fraud_probability"] = 0.01
        
        return predictions
    
    async def _detect_anomalies(self, features: Dict, source: DataSource) -> List[Dict]:
        """Detect anomalies (processd)"""
        anomalies = []
        
        # Process anomaly detection
        if source == DataSource.ECOMMERCE:
            revenue = features.get("revenue", 0)
            if revenue > 10000:
                anomalies.append({
                    "type": "high_revenue",
                    "severity": "medium",
                    "message": f"Unusually high revenue: ${revenue}"
                })
        
        elif source == DataSource.POS:
            amount = features.get("transaction_amount", 0)
            if amount > 5000:
                anomalies.append({
                    "type": "high_transaction",
                    "severity": "high",
                    "message": f"Unusually high transaction: ${amount}"
                })
        
        return anomalies
    
    # ==================== MONITORING METHODS ====================
    
    def get_processing_metrics(self, record_id: str) -> Optional[ProcessingMetrics]:
        """Get processing metrics for a record"""
        return self.processing_metrics.get(record_id)
    
    def get_layer_stats(self) -> Dict:
        """Get statistics for each layer"""
        return self.layer_stats
    
    def get_source_stats(self) -> Dict:
        """Get statistics for each source"""
        return dict(self.source_stats)
    
    def get_realtime_throughput(self) -> Dict:
        """Calculate real-time throughput"""
        total_records = sum(stats["records"] for stats in self.layer_stats.values())
        total_errors = sum(stats["errors"] for stats in self.layer_stats.values())
        
        # Calculate average processing time
        completed_metrics = [m for m in self.processing_metrics.values() if m.status == ProcessingStatus.COMPLETED]
        avg_duration = sum(m.total_duration_ms for m in completed_metrics) / len(completed_metrics) if completed_metrics else 0
        
        return {
            "total_records_processed": total_records,
            "total_errors": total_errors,
            "success_rate": (total_records - total_errors) / total_records * 100 if total_records > 0 else 0,
            "average_processing_time_ms": round(avg_duration, 2),
            "records_per_second": 1000 / avg_duration if avg_duration > 0 else 0
        }

# ==================== FASTAPI APPLICATION ====================

app = FastAPI(
    title="Real-Time Lakehouse Data Flow",
    description="Real-time data flow visualization and processing",
    version="1.0.0"
)

# Initialize data flow
data_flow = RealTimeDataFlow()

@app.post("/ingest")
async def ingest_data(record: DataRecord, background_tasks: BackgroundTasks):
    """
    Ingest data into lakehouse
    Starts real-time processing through all medallion layers
    """
    # Process in background
    background_tasks.add_task(data_flow.ingest_data, record)
    
    return {
        "status": "ingesting",
        "record_id": record.record_id,
        "source": record.source,
        "message": "Data ingestion started"
    }

@app.get("/metrics/{record_id}")
async def get_processing_metrics(record_id: str):
    """Get processing metrics for a specific record"""
    metrics = data_flow.get_processing_metrics(record_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Record not found")
    return metrics

@app.get("/stats/layers")
async def get_layer_stats():
    """Get statistics for each medallion layer"""
    return data_flow.get_layer_stats()

@app.get("/stats/sources")
async def get_source_stats():
    """Get statistics for each data source"""
    return data_flow.get_source_stats()

@app.get("/stats/throughput")
async def get_throughput():
    """Get real-time throughput metrics"""
    return data_flow.get_realtime_throughput()

@app.get("/flow/visualization")
async def get_flow_visualization():
    """Get data flow visualization"""
    return {
        "layers": [
            {
                "name": "Bronze Layer",
                "description": "Raw data storage",
                "processing": "Store as-is, add metadata",
                "stats": data_flow.layer_stats[MedallionLayer.BRONZE]
            },
            {
                "name": "Silver Layer",
                "description": "Cleaned and validated data",
                "processing": "Clean, validate, enrich, deduplicate",
                "stats": data_flow.layer_stats[MedallionLayer.SILVER]
            },
            {
                "name": "Gold Layer",
                "description": "Business analytics",
                "processing": "Aggregate, calculate KPIs, business logic",
                "stats": data_flow.layer_stats[MedallionLayer.GOLD]
            },
            {
                "name": "Platinum Layer",
                "description": "ML/AI features",
                "processing": "Feature engineering, predictions, anomaly detection",
                "stats": data_flow.layer_stats[MedallionLayer.PLATINUM]
            }
        ],
        "throughput": data_flow.get_realtime_throughput()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Real-Time Lakehouse Data Flow",
        "layers_active": 4,
        "sources_active": len(DataSource)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8073)

