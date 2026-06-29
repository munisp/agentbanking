import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Transaction History Service for Remittance Platform
Provides comprehensive transaction tracking, querying, and historical analysis
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import math

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("transaction-history-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import aioredis
from opensearchpy import AsyncOpenSearch
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/transaction_history")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    FEE = "fee"
    INTEREST = "interest"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"

class TransactionChannel(str, Enum):
    AGENT = "agent"
    ATM = "atm"
    MOBILE = "mobile"
    WEB = "web"
    POS = "pos"
    BRANCH = "branch"
    API = "api"

@dataclass
class TransactionFilter:
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    customer_id: Optional[str] = None
    agent_id: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    status: Optional[TransactionStatus] = None
    channel: Optional[TransactionChannel] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    reference_number: Optional[str] = None
    account_number: Optional[str] = None

@dataclass
class TransactionSummary:
    total_transactions: int
    total_amount: float
    average_amount: float
    transaction_types: Dict[str, int]
    status_distribution: Dict[str, int]
    channel_distribution: Dict[str, int]
    daily_volumes: List[Dict[str, Any]]
    top_customers: List[Dict[str, Any]]
    top_agents: List[Dict[str, Any]]

class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String, nullable=False, unique=True, index=True)
    customer_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, index=True)
    account_number = Column(String, index=True)
    transaction_type = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False, index=True)
    currency = Column(String, default="USD")
    description = Column(Text)
    reference_number = Column(String, index=True)
    status = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)
    location = Column(JSON)  # GPS coordinates, branch info, etc.
    metadata = Column(JSON)  # Additional transaction data
    fees = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    exchange_rate = Column(Float)
    original_amount = Column(Float)
    original_currency = Column(String)
    balance_before = Column(Float)
    balance_after = Column(Float)
    fraud_score = Column(Float)
    risk_level = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, index=True)
    settled_at = Column(DateTime)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_customer_date', 'customer_id', 'created_at'),
        Index('idx_agent_date', 'agent_id', 'created_at'),
        Index('idx_type_status', 'transaction_type', 'status'),
        Index('idx_amount_date', 'amount', 'created_at'),
        Index('idx_reference', 'reference_number'),
    )

class TransactionAudit(Base):
    __tablename__ = "transaction_audit"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, STATUS_CHANGE
    old_values = Column(JSON)
    new_values = Column(JSON)
    changed_by = Column(String, nullable=False)
    change_reason = Column(Text)
    ip_address = Column(String)
    user_agent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class TransactionReconciliation(Base):
    __tablename__ = "transaction_reconciliation"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(String, nullable=False, index=True)
    transaction_id = Column(String, nullable=False, index=True)
    external_reference = Column(String)
    reconciliation_status = Column(String, default="pending")  # pending, matched, unmatched, disputed
    reconciled_amount = Column(Float)
    variance = Column(Float)
    reconciled_by = Column(String)
    reconciled_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class TransactionHistoryService:
    def __init__(self):
        self.redis_client = None
        self.opensearch_client = None
        
    async def initialize(self):
        """Initialize the transaction history service"""
        try:
            # Initialize Redis for caching
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            # Initialize OpenSearch for advanced search
            opensearch_url = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
            self.opensearch_client = AsyncOpenSearch([opensearch_url])
            
            # Create OpenSearch index
            await self.create_opensearch_index()
            
            logger.info("Transaction History Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Transaction History Service: {e}")
            # Continue without Redis/OpenSearch if not available
            self.redis_client = None
            self.opensearch_client = None
    
    async def create_opensearch_index(self):
        """Create OpenSearch index for transaction search"""
        if not self.opensearch_client:
            return
        
        index_mapping = {
            "mappings": {
                "properties": {
                    "transaction_id": {"type": "keyword"},
                    "customer_id": {"type": "keyword"},
                    "agent_id": {"type": "keyword"},
                    "account_number": {"type": "keyword"},
                    "transaction_type": {"type": "keyword"},
                    "amount": {"type": "double"},
                    "currency": {"type": "keyword"},
                    "description": {"type": "text"},
                    "reference_number": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "channel": {"type": "keyword"},
                    "location": {"type": "geo_point"},
                    "created_at": {"type": "date"},
                    "processed_at": {"type": "date"},
                    "fraud_score": {"type": "double"},
                    "risk_level": {"type": "keyword"},
                }
            }
        }
        
        try:
            await self.opensearch_client.indices.create(
                index="transactions",
                body=index_mapping,
                ignore=400  # Ignore if index already exists
            )
        except Exception as e:
            logger.error(f"Failed to create OpenSearch index: {e}")
    
    async def record_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """Record a new transaction in history"""
        db = SessionLocal()
        try:
            # Create transaction history record
            transaction = TransactionHistory(
                transaction_id=transaction_data.get("transaction_id", str(uuid.uuid4())),
                customer_id=transaction_data["customer_id"],
                agent_id=transaction_data.get("agent_id"),
                account_number=transaction_data.get("account_number"),
                transaction_type=transaction_data["transaction_type"],
                amount=transaction_data["amount"],
                currency=transaction_data.get("currency", "USD"),
                description=transaction_data.get("description"),
                reference_number=transaction_data.get("reference_number"),
                status=transaction_data.get("status", TransactionStatus.PENDING.value),
                channel=transaction_data.get("channel", TransactionChannel.AGENT.value),
                location=transaction_data.get("location"),
                metadata=transaction_data.get("metadata"),
                fees=transaction_data.get("fees", 0.0),
                commission=transaction_data.get("commission", 0.0),
                exchange_rate=transaction_data.get("exchange_rate"),
                original_amount=transaction_data.get("original_amount"),
                original_currency=transaction_data.get("original_currency"),
                balance_before=transaction_data.get("balance_before"),
                balance_after=transaction_data.get("balance_after"),
                fraud_score=transaction_data.get("fraud_score"),
                risk_level=transaction_data.get("risk_level"),
                processed_at=transaction_data.get("processed_at"),
                settled_at=transaction_data.get("settled_at"),
            )
            
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            
            # Index in OpenSearch for search
            await self.index_transaction_in_opensearch(transaction)
            
            # Clear relevant caches
            await self.invalidate_cache(transaction.customer_id, transaction.agent_id)
            
            return transaction.transaction_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to record transaction: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def update_transaction_status(self, transaction_id: str, status: TransactionStatus,
                                      updated_by: str, reason: str = None) -> bool:
        """Update transaction status with audit trail"""
        db = SessionLocal()
        try:
            transaction = db.query(TransactionHistory).filter(
                TransactionHistory.transaction_id == transaction_id
            ).first()
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            old_status = transaction.status
            old_values = {"status": old_status}
            new_values = {"status": status.value}
            
            # Update transaction
            transaction.status = status.value
            transaction.updated_at = datetime.utcnow()
            
            if status == TransactionStatus.COMPLETED:
                transaction.processed_at = datetime.utcnow()
            
            # Create audit record
            audit = TransactionAudit(
                transaction_id=transaction_id,
                action="STATUS_CHANGE",
                old_values=old_values,
                new_values=new_values,
                changed_by=updated_by,
                change_reason=reason,
                timestamp=datetime.utcnow()
            )
            
            db.add(audit)
            db.commit()
            
            # Update in OpenSearch
            await self.update_transaction_in_opensearch(transaction)
            
            # Clear caches
            await self.invalidate_cache(transaction.customer_id, transaction.agent_id)
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update transaction status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def get_transaction_history(self, filters: TransactionFilter,
                                    page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """Get transaction history with filtering and pagination"""
        db = SessionLocal()
        try:
            # Build query
            query = db.query(TransactionHistory)
            
            # Apply filters
            if filters.start_date:
                query = query.filter(TransactionHistory.created_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(TransactionHistory.created_at <= filters.end_date)
            if filters.customer_id:
                query = query.filter(TransactionHistory.customer_id == filters.customer_id)
            if filters.agent_id:
                query = query.filter(TransactionHistory.agent_id == filters.agent_id)
            if filters.transaction_type:
                query = query.filter(TransactionHistory.transaction_type == filters.transaction_type.value)
            if filters.status:
                query = query.filter(TransactionHistory.status == filters.status.value)
            if filters.channel:
                query = query.filter(TransactionHistory.channel == filters.channel.value)
            if filters.min_amount:
                query = query.filter(TransactionHistory.amount >= filters.min_amount)
            if filters.max_amount:
                query = query.filter(TransactionHistory.amount <= filters.max_amount)
            if filters.reference_number:
                query = query.filter(TransactionHistory.reference_number == filters.reference_number)
            if filters.account_number:
                query = query.filter(TransactionHistory.account_number == filters.account_number)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * limit
            transactions = query.order_by(TransactionHistory.created_at.desc()).offset(offset).limit(limit).all()
            
            # Convert to dict
            transaction_list = []
            for txn in transactions:
                transaction_dict = {
                    "id": str(txn.id),
                    "transaction_id": txn.transaction_id,
                    "customer_id": txn.customer_id,
                    "agent_id": txn.agent_id,
                    "account_number": txn.account_number,
                    "transaction_type": txn.transaction_type,
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "description": txn.description,
                    "reference_number": txn.reference_number,
                    "status": txn.status,
                    "channel": txn.channel,
                    "location": txn.location,
                    "metadata": txn.metadata,
                    "fees": txn.fees,
                    "commission": txn.commission,
                    "balance_before": txn.balance_before,
                    "balance_after": txn.balance_after,
                    "fraud_score": txn.fraud_score,
                    "risk_level": txn.risk_level,
                    "created_at": txn.created_at.isoformat(),
                    "updated_at": txn.updated_at.isoformat(),
                    "processed_at": txn.processed_at.isoformat() if txn.processed_at else None,
                    "settled_at": txn.settled_at.isoformat() if txn.settled_at else None,
                }
                transaction_list.append(transaction_dict)
            
            return {
                "transactions": transaction_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": math.ceil(total_count / limit),
                    "has_next": page * limit < total_count,
                    "has_prev": page > 1,
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def get_transaction_summary(self, filters: TransactionFilter) -> TransactionSummary:
        """Get transaction summary and analytics"""
        cache_key = f"transaction_summary:{hash(str(filters))}"
        
        # Try cache first
        if self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return TransactionSummary(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        
        db = SessionLocal()
        try:
            # Build base query
            query = db.query(TransactionHistory)
            
            # Apply filters
            if filters.start_date:
                query = query.filter(TransactionHistory.created_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(TransactionHistory.created_at <= filters.end_date)
            if filters.customer_id:
                query = query.filter(TransactionHistory.customer_id == filters.customer_id)
            if filters.agent_id:
                query = query.filter(TransactionHistory.agent_id == filters.agent_id)
            if filters.transaction_type:
                query = query.filter(TransactionHistory.transaction_type == filters.transaction_type.value)
            if filters.status:
                query = query.filter(TransactionHistory.status == filters.status.value)
            if filters.channel:
                query = query.filter(TransactionHistory.channel == filters.channel.value)
            
            # Get all transactions for analysis
            transactions = query.all()
            
            if not transactions:
                return TransactionSummary(
                    total_transactions=0,
                    total_amount=0.0,
                    average_amount=0.0,
                    transaction_types={},
                    status_distribution={},
                    channel_distribution={},
                    daily_volumes=[],
                    top_customers=[],
                    top_agents=[]
                )
            
            # Calculate summary statistics
            total_transactions = len(transactions)
            total_amount = sum(txn.amount for txn in transactions)
            average_amount = total_amount / total_transactions if total_transactions > 0 else 0
            
            # Transaction type distribution
            transaction_types = {}
            for txn in transactions:
                transaction_types[txn.transaction_type] = transaction_types.get(txn.transaction_type, 0) + 1
            
            # Status distribution
            status_distribution = {}
            for txn in transactions:
                status_distribution[txn.status] = status_distribution.get(txn.status, 0) + 1
            
            # Channel distribution
            channel_distribution = {}
            for txn in transactions:
                channel_distribution[txn.channel] = channel_distribution.get(txn.channel, 0) + 1
            
            # Daily volumes
            daily_volumes = self.calculate_daily_volumes(transactions)
            
            # Top customers by transaction volume
            top_customers = self.get_top_customers(transactions)
            
            # Top agents by transaction volume
            top_agents = self.get_top_agents(transactions)
            
            summary = TransactionSummary(
                total_transactions=total_transactions,
                total_amount=total_amount,
                average_amount=average_amount,
                transaction_types=transaction_types,
                status_distribution=status_distribution,
                channel_distribution=channel_distribution,
                daily_volumes=daily_volumes,
                top_customers=top_customers,
                top_agents=top_agents
            )
            
            # Cache the result
            if self.redis_client:
                try:
                    await self.redis_client.setex(
                        cache_key,
                        300,  # 5 minutes
                        json.dumps(asdict(summary))
                    )
                except Exception as e:
                    logger.warning(f"Cache write failed: {e}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get transaction summary: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    def calculate_daily_volumes(self, transactions: List[TransactionHistory]) -> List[Dict[str, Any]]:
        """Calculate daily transaction volumes"""
        daily_data = {}
        
        for txn in transactions:
            date_key = txn.created_at.date().isoformat()
            if date_key not in daily_data:
                daily_data[date_key] = {"date": date_key, "count": 0, "amount": 0.0}
            
            daily_data[date_key]["count"] += 1
            daily_data[date_key]["amount"] += txn.amount
        
        return sorted(daily_data.values(), key=lambda x: x["date"])
    
    def get_top_customers(self, transactions: List[TransactionHistory], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top customers by transaction volume"""
        customer_data = {}
        
        for txn in transactions:
            if txn.customer_id not in customer_data:
                customer_data[txn.customer_id] = {
                    "customer_id": txn.customer_id,
                    "transaction_count": 0,
                    "total_amount": 0.0
                }
            
            customer_data[txn.customer_id]["transaction_count"] += 1
            customer_data[txn.customer_id]["total_amount"] += txn.amount
        
        # Sort by total amount and return top customers
        sorted_customers = sorted(
            customer_data.values(),
            key=lambda x: x["total_amount"],
            reverse=True
        )
        
        return sorted_customers[:limit]
    
    def get_top_agents(self, transactions: List[TransactionHistory], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top agents by transaction volume"""
        agent_data = {}
        
        for txn in transactions:
            if txn.agent_id:
                if txn.agent_id not in agent_data:
                    agent_data[txn.agent_id] = {
                        "agent_id": txn.agent_id,
                        "transaction_count": 0,
                        "total_amount": 0.0,
                        "commission_earned": 0.0
                    }
                
                agent_data[txn.agent_id]["transaction_count"] += 1
                agent_data[txn.agent_id]["total_amount"] += txn.amount
                agent_data[txn.agent_id]["commission_earned"] += txn.commission or 0.0
        
        # Sort by total amount and return top agents
        sorted_agents = sorted(
            agent_data.values(),
            key=lambda x: x["total_amount"],
            reverse=True
        )
        
        return sorted_agents[:limit]
    
    async def search_transactions(self, query: str, filters: TransactionFilter = None,
                                page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """Search transactions using OpenSearch"""
        if not self.opensearch_client:
            # Fallback to database search
            return await self.database_search_transactions(query, filters, page, limit)
        
        try:
            # Build OpenSearch query
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "description^2",
                                        "reference_number^3",
                                        "transaction_id^3",
                                        "customer_id",
                                        "agent_id",
                                        "account_number"
                                    ]
                                }
                            }
                        ],
                        "filter": []
                    }
                },
                "sort": [{"created_at": {"order": "desc"}}],
                "from": (page - 1) * limit,
                "size": limit
            }
            
            # Apply filters
            if filters:
                if filters.start_date:
                    es_query["query"]["bool"]["filter"].append({
                        "range": {"created_at": {"gte": filters.start_date.isoformat()}}
                    })
                if filters.end_date:
                    es_query["query"]["bool"]["filter"].append({
                        "range": {"created_at": {"lte": filters.end_date.isoformat()}}
                    })
                if filters.customer_id:
                    es_query["query"]["bool"]["filter"].append({
                        "term": {"customer_id": filters.customer_id}
                    })
                if filters.transaction_type:
                    es_query["query"]["bool"]["filter"].append({
                        "term": {"transaction_type": filters.transaction_type.value}
                    })
                if filters.status:
                    es_query["query"]["bool"]["filter"].append({
                        "term": {"status": filters.status.value}
                    })
            
            # Execute search
            response = await self.opensearch_client.search(
                index="transactions",
                body=es_query
            )
            
            # Process results
            transactions = []
            for hit in response["hits"]["hits"]:
                transactions.append(hit["_source"])
            
            total_count = response["hits"]["total"]["value"]
            
            return {
                "transactions": transactions,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": math.ceil(total_count / limit),
                    "has_next": page * limit < total_count,
                    "has_prev": page > 1,
                }
            }
            
        except Exception as e:
            logger.error(f"OpenSearch search failed: {e}")
            # Fallback to database search
            return await self.database_search_transactions(query, filters, page, limit)
    
    async def database_search_transactions(self, query: str, filters: TransactionFilter = None,
                                         page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """Fallback database search for transactions"""
        db = SessionLocal()
        try:
            # Build database query
            db_query = db.query(TransactionHistory)
            
            # Add text search conditions
            search_conditions = []
            search_conditions.append(TransactionHistory.description.ilike(f"%{query}%"))
            search_conditions.append(TransactionHistory.reference_number.ilike(f"%{query}%"))
            search_conditions.append(TransactionHistory.transaction_id.ilike(f"%{query}%"))
            search_conditions.append(TransactionHistory.customer_id.ilike(f"%{query}%"))
            
            from sqlalchemy import or_
            db_query = db_query.filter(or_(*search_conditions))
            
            # Apply additional filters
            if filters:
                if filters.start_date:
                    db_query = db_query.filter(TransactionHistory.created_at >= filters.start_date)
                if filters.end_date:
                    db_query = db_query.filter(TransactionHistory.created_at <= filters.end_date)
                if filters.customer_id:
                    db_query = db_query.filter(TransactionHistory.customer_id == filters.customer_id)
                if filters.transaction_type:
                    db_query = db_query.filter(TransactionHistory.transaction_type == filters.transaction_type.value)
                if filters.status:
                    db_query = db_query.filter(TransactionHistory.status == filters.status.value)
            
            # Get total count
            total_count = db_query.count()
            
            # Apply pagination
            offset = (page - 1) * limit
            transactions = db_query.order_by(TransactionHistory.created_at.desc()).offset(offset).limit(limit).all()
            
            # Convert to dict
            transaction_list = []
            for txn in transactions:
                transaction_dict = {
                    "transaction_id": txn.transaction_id,
                    "customer_id": txn.customer_id,
                    "agent_id": txn.agent_id,
                    "transaction_type": txn.transaction_type,
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "description": txn.description,
                    "status": txn.status,
                    "created_at": txn.created_at.isoformat(),
                }
                transaction_list.append(transaction_dict)
            
            return {
                "transactions": transaction_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": math.ceil(total_count / limit),
                    "has_next": page * limit < total_count,
                    "has_prev": page > 1,
                }
            }
            
        except Exception as e:
            logger.error(f"Database search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def get_transaction_audit_trail(self, transaction_id: str) -> List[Dict[str, Any]]:
        """Get audit trail for a specific transaction"""
        db = SessionLocal()
        try:
            audit_records = db.query(TransactionAudit).filter(
                TransactionAudit.transaction_id == transaction_id
            ).order_by(TransactionAudit.timestamp.desc()).all()
            
            audit_trail = []
            for record in audit_records:
                audit_trail.append({
                    "id": str(record.id),
                    "action": record.action,
                    "old_values": record.old_values,
                    "new_values": record.new_values,
                    "changed_by": record.changed_by,
                    "change_reason": record.change_reason,
                    "ip_address": record.ip_address,
                    "user_agent": record.user_agent,
                    "timestamp": record.timestamp.isoformat(),
                })
            
            return audit_trail
            
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def index_transaction_in_opensearch(self, transaction: TransactionHistory):
        """Index transaction in OpenSearch for search"""
        if not self.opensearch_client:
            return
        
        try:
            doc = {
                "transaction_id": transaction.transaction_id,
                "customer_id": transaction.customer_id,
                "agent_id": transaction.agent_id,
                "account_number": transaction.account_number,
                "transaction_type": transaction.transaction_type,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "description": transaction.description,
                "reference_number": transaction.reference_number,
                "status": transaction.status,
                "channel": transaction.channel,
                "location": transaction.location,
                "created_at": transaction.created_at.isoformat(),
                "processed_at": transaction.processed_at.isoformat() if transaction.processed_at else None,
                "fraud_score": transaction.fraud_score,
                "risk_level": transaction.risk_level,
            }
            
            await self.opensearch_client.index(
                index="transactions",
                id=transaction.transaction_id,
                body=doc
            )
            
        except Exception as e:
            logger.error(f"Failed to index transaction in OpenSearch: {e}")
    
    async def update_transaction_in_opensearch(self, transaction: TransactionHistory):
        """Update transaction in OpenSearch"""
        if not self.opensearch_client:
            return
        
        try:
            doc = {
                "status": transaction.status,
                "updated_at": transaction.updated_at.isoformat(),
                "processed_at": transaction.processed_at.isoformat() if transaction.processed_at else None,
            }
            
            await self.opensearch_client.update(
                index="transactions",
                id=transaction.transaction_id,
                body={"doc": doc}
            )
            
        except Exception as e:
            logger.error(f"Failed to update transaction in OpenSearch: {e}")
    
    async def invalidate_cache(self, customer_id: str = None, agent_id: str = None):
        """Invalidate relevant caches"""
        if not self.redis_client:
            return
        
        try:
            # Invalidate summary caches
            keys_to_delete = []
            
            if customer_id:
                keys_to_delete.extend([
                    f"customer_summary:{customer_id}",
                    f"customer_transactions:{customer_id}:*"
                ])
            
            if agent_id:
                keys_to_delete.extend([
                    f"agent_summary:{agent_id}",
                    f"agent_transactions:{agent_id}:*"
                ])
            
            # Delete general summary caches
            keys_to_delete.append("transaction_summary:*")
            
            for pattern in keys_to_delete:
                if "*" in pattern:
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                else:
                    await self.redis_client.delete(pattern)
                    
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db = SessionLocal()
        try:
            # Check database connection
            db.execute("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False
        finally:
            db.close()
        
        # Check Redis connection
        redis_healthy = False
        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception:
                redis_healthy = False
        
        # Check OpenSearch connection
        opensearch_healthy = False
        if self.opensearch_client:
            try:
                await self.opensearch_client.ping()
                opensearch_healthy = True
            except Exception:
                opensearch_healthy = False
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "transaction-history-service",
            "version": "1.0.0",
            "components": {
                "database": db_healthy,
                "redis": redis_healthy,
                "opensearch": es_healthy,
            }
        }

# FastAPI application
app = FastAPI(title="Transaction History Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
transaction_service = TransactionHistoryService()

# Pydantic models for API
class TransactionRecordModel(BaseModel):
    transaction_id: Optional[str] = None
    customer_id: str
    agent_id: Optional[str] = None
    account_number: Optional[str] = None
    transaction_type: TransactionType
    amount: float
    currency: str = "USD"
    description: Optional[str] = None
    reference_number: Optional[str] = None
    status: TransactionStatus = TransactionStatus.PENDING
    channel: TransactionChannel = TransactionChannel.AGENT
    location: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    fees: float = 0.0
    commission: float = 0.0
    balance_before: Optional[float] = None
    balance_after: Optional[float] = None
    fraud_score: Optional[float] = None
    risk_level: Optional[str] = None

class TransactionFilterModel(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    customer_id: Optional[str] = None
    agent_id: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    status: Optional[TransactionStatus] = None
    channel: Optional[TransactionChannel] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    reference_number: Optional[str] = None
    account_number: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await transaction_service.initialize()

@app.post("/record-transaction")
async def record_transaction(transaction: TransactionRecordModel):
    """Record a new transaction"""
    transaction_id = await transaction_service.record_transaction(transaction.dict())
    return {"transaction_id": transaction_id, "status": "recorded"}

@app.put("/transactions/{transaction_id}/status")
async def update_transaction_status(
    transaction_id: str,
    status: TransactionStatus,
    updated_by: str = Query(...),
    reason: Optional[str] = Query(None)
):
    """Update transaction status"""
    success = await transaction_service.update_transaction_status(
        transaction_id, status, updated_by, reason
    )
    return {"success": success}

@app.post("/transactions/history")
async def get_transaction_history(
    filters: TransactionFilterModel,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000)
):
    """Get transaction history with filtering"""
    filter_obj = TransactionFilter(**filters.dict())
    return await transaction_service.get_transaction_history(filter_obj, page, limit)

@app.post("/transactions/summary")
async def get_transaction_summary(filters: TransactionFilterModel):
    """Get transaction summary and analytics"""
    filter_obj = TransactionFilter(**filters.dict())
    summary = await transaction_service.get_transaction_summary(filter_obj)
    return asdict(summary)

@app.get("/transactions/search")
async def search_transactions(
    q: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    customer_id: Optional[str] = Query(None),
    transaction_type: Optional[TransactionType] = Query(None),
    status: Optional[TransactionStatus] = Query(None)
):
    """Search transactions"""
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        transaction_type=transaction_type,
        status=status
    )
    return await transaction_service.search_transactions(q, filters, page, limit)

@app.get("/transactions/{transaction_id}/audit")
async def get_transaction_audit_trail(transaction_id: str):
    """Get audit trail for a transaction"""
    audit_trail = await transaction_service.get_transaction_audit_trail(transaction_id)
    return {"transaction_id": transaction_id, "audit_trail": audit_trail}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await transaction_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
