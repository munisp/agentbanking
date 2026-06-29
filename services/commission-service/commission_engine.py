import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Commission Calculation Engine and Rules Management System
Handles real-time commission calculations, rule management, and hierarchical commission distribution
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query, Path, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("commission-calculation-engine")
app.include_router(metrics_router)

from pydantic import BaseModel, validator, Field
import json
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Commission Calculation Engine",
    description="Advanced commission calculation and rules management system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://banking_user:banking_pass@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Database and Redis connections
db_pool = None
redis_client = None

# =====================================================
# ENUMS AND CONSTANTS
# =====================================================

class CommissionType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    TIERED = "tiered"
    HYBRID = "hybrid"

class CommissionFrequency(str, Enum):
    PER_TRANSACTION = "per_transaction"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class CalculationStatus(str, Enum):
    CALCULATED = "calculated"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentTier(str, Enum):
    SUPER_AGENT = "super_agent"
    SENIOR_AGENT = "senior_agent"
    AGENT = "agent"
    SUB_AGENT = "sub_agent"
    TRAINEE = "trainee"

# =====================================================
# DATA MODELS
# =====================================================

class CommissionRuleCreate(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    agent_tier: Optional[AgentTier] = None
    transaction_type: Optional[str] = None
    transaction_channel: Optional[str] = None
    min_amount: Optional[Decimal] = Field(None, ge=0)
    max_amount: Optional[Decimal] = Field(None, ge=0)
    territory_id: Optional[str] = None
    commission_type: CommissionType
    commission_value: Decimal = Field(..., ge=0)
    fixed_amount: Optional[Decimal] = Field(None, ge=0)
    percentage_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    tier_structure: Optional[Dict[str, Any]] = None
    frequency: CommissionFrequency = CommissionFrequency.PER_TRANSACTION
    max_commission_per_transaction: Optional[Decimal] = Field(None, ge=0)
    max_commission_per_day: Optional[Decimal] = Field(None, ge=0)
    max_commission_per_month: Optional[Decimal] = Field(None, ge=0)
    hierarchy_commission_enabled: bool = False
    hierarchy_commission_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    hierarchy_max_levels: int = Field(1, ge=1, le=10)
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    priority: int = Field(100, ge=1, le=1000)

    @validator('max_amount')
    def validate_amount_range(cls, v, values):
        if v is not None and 'min_amount' in values and values['min_amount'] is not None:
            if v <= values['min_amount']:
                raise ValueError('max_amount must be greater than min_amount')
        return v

    @validator('percentage_rate')
    def validate_percentage_commission(cls, v, values):
        if values.get('commission_type') == CommissionType.PERCENTAGE and v is None:
            raise ValueError('percentage_rate is required for percentage commission type')
        return v

    @validator('fixed_amount')
    def validate_fixed_commission(cls, v, values):
        if values.get('commission_type') == CommissionType.FIXED and v is None:
            raise ValueError('fixed_amount is required for fixed commission type')
        return v

class CommissionRuleResponse(BaseModel):
    id: str
    rule_name: str
    description: Optional[str]
    agent_tier: Optional[str]
    transaction_type: Optional[str]
    transaction_channel: Optional[str]
    min_amount: Optional[Decimal]
    max_amount: Optional[Decimal]
    territory_id: Optional[str]
    commission_type: str
    commission_value: Decimal
    fixed_amount: Optional[Decimal]
    percentage_rate: Optional[Decimal]
    tier_structure: Optional[Dict[str, Any]]
    frequency: str
    max_commission_per_transaction: Optional[Decimal]
    max_commission_per_day: Optional[Decimal]
    max_commission_per_month: Optional[Decimal]
    hierarchy_commission_enabled: bool
    hierarchy_commission_rate: Optional[Decimal]
    hierarchy_max_levels: int
    is_active: bool
    effective_from: datetime
    effective_until: Optional[datetime]
    priority: int
    created_at: datetime
    updated_at: datetime

class TransactionData(BaseModel):
    transaction_id: str
    agent_id: str
    transaction_amount: Decimal = Field(..., gt=0)
    transaction_type: str
    transaction_channel: Optional[str] = None
    transaction_date: Optional[datetime] = None
    customer_id: Optional[str] = None
    merchant_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CommissionCalculationRequest(BaseModel):
    transaction_data: TransactionData
    force_recalculation: bool = False

class CommissionCalculationResult(BaseModel):
    calculation_id: str
    transaction_id: str
    agent_id: str
    rule_id: str
    commission_amount: Decimal
    commission_rate: Optional[Decimal]
    calculation_method: str
    calculation_details: Dict[str, Any]
    hierarchy_commissions: List[Dict[str, Any]] = []
    total_commission: Decimal
    status: str
    calculated_at: datetime

class TieredCommission(BaseModel):
    min_amount: Decimal
    max_amount: Optional[Decimal]
    rate: Decimal
    fixed_amount: Optional[Decimal] = None

class CommissionSummary(BaseModel):
    agent_id: str
    period_start: date
    period_end: date
    total_transactions: int
    total_volume: Decimal
    gross_commission: Decimal
    hierarchy_commission: Decimal
    net_commission: Decimal
    avg_commission_rate: Decimal

# =====================================================
# DATABASE CONNECTION
# =====================================================

async def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return await db_pool.acquire()

async def get_redis_connection():
    """Get Redis connection"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

# =====================================================
# COMMISSION CALCULATION ENGINE
# =====================================================

class CommissionCalculationEngine:
    """Advanced commission calculation engine with support for multiple calculation methods"""
    
    def __init__(self, db_connection, redis_connection):
        self.db = db_connection
        self.redis = redis_connection
    
    async def calculate_commission(self, transaction_data: TransactionData) -> CommissionCalculationResult:
        """Main commission calculation method"""
        try:
            # Get applicable commission rules
            rules = await self._get_applicable_rules(transaction_data)
            
            if not rules:
                logger.warning(f"No commission rules found for transaction {transaction_data.transaction_id}")
                return await self._create_zero_commission_result(transaction_data)
            
            # Select the best rule based on priority
            selected_rule = max(rules, key=lambda r: r['priority'])
            
            # Calculate primary commission
            primary_commission = await self._calculate_primary_commission(transaction_data, selected_rule)
            
            # Calculate hierarchy commissions if enabled
            hierarchy_commissions = []
            if selected_rule['hierarchy_commission_enabled']:
                hierarchy_commissions = await self._calculate_hierarchy_commissions(
                    transaction_data, selected_rule, primary_commission
                )
            
            # Create calculation result
            calculation_id = str(uuid.uuid4())
            total_commission = primary_commission['amount'] + sum(hc['amount'] for hc in hierarchy_commissions)
            
            # Store calculation in database
            await self._store_calculation_result(
                calculation_id, transaction_data, selected_rule, 
                primary_commission, hierarchy_commissions, total_commission
            )
            
            # Cache result in Redis
            await self._cache_calculation_result(calculation_id, {
                'transaction_id': transaction_data.transaction_id,
                'agent_id': transaction_data.agent_id,
                'total_commission': float(total_commission),
                'calculated_at': datetime.utcnow().isoformat()
            })
            
            return CommissionCalculationResult(
                calculation_id=calculation_id,
                transaction_id=transaction_data.transaction_id,
                agent_id=transaction_data.agent_id,
                rule_id=str(selected_rule['id']),
                commission_amount=primary_commission['amount'],
                commission_rate=primary_commission.get('rate'),
                calculation_method=primary_commission['method'],
                calculation_details=primary_commission['details'],
                hierarchy_commissions=hierarchy_commissions,
                total_commission=total_commission,
                status=CalculationStatus.CALCULATED,
                calculated_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Commission calculation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Commission calculation failed: {str(e)}")
    
    async def _get_applicable_rules(self, transaction_data: TransactionData) -> List[Dict]:
        """Get all applicable commission rules for a transaction"""
        # Get agent details
        agent_query = "SELECT tier, territory_id FROM agents WHERE id = $1"
        agent_result = await self.db.fetchrow(agent_query, transaction_data.agent_id)
        
        if not agent_result:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Build rule matching query
        rules_query = """
        SELECT * FROM commission_rules 
        WHERE is_active = true 
        AND (effective_from IS NULL OR effective_from <= $1)
        AND (effective_until IS NULL OR effective_until >= $1)
        AND (agent_tier IS NULL OR agent_tier = $2)
        AND (transaction_type IS NULL OR transaction_type = $3)
        AND (transaction_channel IS NULL OR transaction_channel = $4)
        AND (min_amount IS NULL OR min_amount <= $5)
        AND (max_amount IS NULL OR max_amount >= $5)
        AND (territory_id IS NULL OR territory_id = $6)
        ORDER BY priority DESC
        """
        
        transaction_date = transaction_data.transaction_date or datetime.utcnow()
        
        rules = await self.db.fetch(
            rules_query,
            transaction_date,
            agent_result['tier'],
            transaction_data.transaction_type,
            transaction_data.transaction_channel,
            transaction_data.transaction_amount,
            agent_result['territory_id']
        )
        
        return [dict(rule) for rule in rules]
    
    async def _calculate_primary_commission(self, transaction_data: TransactionData, rule: Dict) -> Dict:
        """Calculate primary commission based on rule type"""
        commission_type = rule['commission_type']
        amount = transaction_data.transaction_amount
        
        if commission_type == CommissionType.PERCENTAGE:
            return await self._calculate_percentage_commission(amount, rule)
        elif commission_type == CommissionType.FIXED:
            return await self._calculate_fixed_commission(amount, rule)
        elif commission_type == CommissionType.TIERED:
            return await self._calculate_tiered_commission(amount, rule)
        elif commission_type == CommissionType.HYBRID:
            return await self._calculate_hybrid_commission(amount, rule)
        else:
            raise ValueError(f"Unsupported commission type: {commission_type}")
    
    async def _calculate_percentage_commission(self, amount: Decimal, rule: Dict) -> Dict:
        """Calculate percentage-based commission"""
        rate = Decimal(str(rule['percentage_rate']))
        commission_amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Apply limits
        if rule['max_commission_per_transaction']:
            commission_amount = min(commission_amount, Decimal(str(rule['max_commission_per_transaction'])))
        
        return {
            'amount': commission_amount,
            'rate': rate,
            'method': 'percentage',
            'details': {
                'transaction_amount': float(amount),
                'commission_rate': float(rate),
                'raw_commission': float(commission_amount),
                'applied_limits': rule['max_commission_per_transaction'] is not None
            }
        }
    
    async def _calculate_fixed_commission(self, amount: Decimal, rule: Dict) -> Dict:
        """Calculate fixed commission"""
        commission_amount = Decimal(str(rule['fixed_amount']))
        
        return {
            'amount': commission_amount,
            'rate': None,
            'method': 'fixed',
            'details': {
                'transaction_amount': float(amount),
                'fixed_commission': float(commission_amount)
            }
        }
    
    async def _calculate_tiered_commission(self, amount: Decimal, rule: Dict) -> Dict:
        """Calculate tiered commission based on amount ranges"""
        tier_structure = rule['tier_structure'] or {}
        tiers = tier_structure.get('tiers', [])
        
        if not tiers:
            raise ValueError("Tiered commission requires tier structure")
        
        # Find applicable tier
        applicable_tier = None
        for tier in tiers:
            min_amt = Decimal(str(tier['min_amount']))
            max_amt = Decimal(str(tier.get('max_amount', float('inf'))))
            
            if min_amt <= amount <= max_amt:
                applicable_tier = tier
                break
        
        if not applicable_tier:
            # Use default tier or zero commission
            applicable_tier = tiers[0] if tiers else {'rate': 0, 'fixed_amount': 0}
        
        # Calculate commission based on tier
        if 'rate' in applicable_tier:
            rate = Decimal(str(applicable_tier['rate']))
            commission_amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            commission_amount = Decimal(str(applicable_tier.get('fixed_amount', 0)))
            rate = None
        
        # Add fixed amount if specified
        if 'fixed_amount' in applicable_tier and 'rate' in applicable_tier:
            commission_amount += Decimal(str(applicable_tier['fixed_amount']))
        
        return {
            'amount': commission_amount,
            'rate': rate,
            'method': 'tiered',
            'details': {
                'transaction_amount': float(amount),
                'applicable_tier': applicable_tier,
                'commission_amount': float(commission_amount)
            }
        }
    
    async def _calculate_hybrid_commission(self, amount: Decimal, rule: Dict) -> Dict:
        """Calculate hybrid commission (combination of percentage and fixed)"""
        percentage_rate = Decimal(str(rule.get('percentage_rate', 0)))
        fixed_amount = Decimal(str(rule.get('fixed_amount', 0)))
        
        percentage_commission = (amount * percentage_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_commission = percentage_commission + fixed_amount
        
        # Apply limits
        if rule['max_commission_per_transaction']:
            total_commission = min(total_commission, Decimal(str(rule['max_commission_per_transaction'])))
        
        return {
            'amount': total_commission,
            'rate': percentage_rate,
            'method': 'hybrid',
            'details': {
                'transaction_amount': float(amount),
                'percentage_rate': float(percentage_rate),
                'percentage_commission': float(percentage_commission),
                'fixed_amount': float(fixed_amount),
                'total_commission': float(total_commission)
            }
        }
    
    async def _calculate_hierarchy_commissions(self, transaction_data: TransactionData, rule: Dict, primary_commission: Dict) -> List[Dict]:
        """Calculate hierarchy commissions for parent agents"""
        hierarchy_commissions = []
        
        if not rule['hierarchy_commission_enabled']:
            return hierarchy_commissions
        
        # Get agent hierarchy
        hierarchy_query = """
        SELECT a.id, a.first_name, a.last_name, a.tier, ah.depth
        FROM agents a
        INNER JOIN agent_hierarchy ah ON a.id = ah.ancestor_id
        WHERE ah.agent_id = $1 AND ah.depth > 0 AND ah.depth <= $2
        ORDER BY ah.depth
        """
        
        hierarchy_agents = await self.db.fetch(
            hierarchy_query, 
            transaction_data.agent_id, 
            rule['hierarchy_max_levels']
        )
        
        hierarchy_rate = Decimal(str(rule.get('hierarchy_commission_rate', 0)))
        
        for agent in hierarchy_agents:
            # Calculate hierarchy commission (percentage of primary commission)
            hierarchy_amount = (primary_commission['amount'] * hierarchy_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            hierarchy_commissions.append({
                'agent_id': agent['id'],
                'agent_name': f"{agent['first_name']} {agent['last_name']}",
                'tier': agent['tier'],
                'hierarchy_level': agent['depth'],
                'amount': hierarchy_amount,
                'rate': hierarchy_rate,
                'calculation_details': {
                    'primary_commission': float(primary_commission['amount']),
                    'hierarchy_rate': float(hierarchy_rate),
                    'hierarchy_commission': float(hierarchy_amount)
                }
            })
        
        return hierarchy_commissions
    
    async def _store_calculation_result(self, calculation_id: str, transaction_data: TransactionData, 
                                      rule: Dict, primary_commission: Dict, hierarchy_commissions: List, 
                                      total_commission: Decimal):
        """Store calculation result in database"""
        # Store primary commission calculation
        await self.db.execute(
            """
            INSERT INTO commission_calculations (
                id, transaction_id, agent_id, rule_id, transaction_amount, transaction_type,
                transaction_channel, transaction_date, commission_amount, commission_rate,
                calculation_method, calculation_details, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            calculation_id, transaction_data.transaction_id, transaction_data.agent_id,
            rule['id'], transaction_data.transaction_amount, transaction_data.transaction_type,
            transaction_data.transaction_channel, transaction_data.transaction_date or datetime.utcnow(),
            primary_commission['amount'], primary_commission.get('rate'),
            primary_commission['method'], json.dumps(primary_commission['details']),
            CalculationStatus.CALCULATED
        )
        
        # Store hierarchy commissions
        for hc in hierarchy_commissions:
            hierarchy_calc_id = str(uuid.uuid4())
            await self.db.execute(
                """
                INSERT INTO commission_calculations (
                    id, transaction_id, agent_id, rule_id, transaction_amount, transaction_type,
                    transaction_channel, transaction_date, commission_amount, commission_rate,
                    calculation_method, calculation_details, parent_agent_id, parent_commission_amount,
                    hierarchy_level, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                hierarchy_calc_id, transaction_data.transaction_id, hc['agent_id'],
                rule['id'], transaction_data.transaction_amount, transaction_data.transaction_type,
                transaction_data.transaction_channel, transaction_data.transaction_date or datetime.utcnow(),
                hc['amount'], hc['rate'], 'hierarchy', json.dumps(hc['calculation_details']),
                transaction_data.agent_id, primary_commission['amount'], hc['hierarchy_level'],
                CalculationStatus.CALCULATED
            )
    
    async def _cache_calculation_result(self, calculation_id: str, result_data: Dict):
        """Cache calculation result in Redis"""
        await self.redis.setex(
            f"commission_calc:{calculation_id}",
            3600,  # 1 hour TTL
            json.dumps(result_data, default=str)
        )
    
    async def _create_zero_commission_result(self, transaction_data: TransactionData) -> CommissionCalculationResult:
        """Create zero commission result when no rules apply"""
        calculation_id = str(uuid.uuid4())
        
        return CommissionCalculationResult(
            calculation_id=calculation_id,
            transaction_id=transaction_data.transaction_id,
            agent_id=transaction_data.agent_id,
            rule_id="",
            commission_amount=Decimal('0.00'),
            commission_rate=None,
            calculation_method="no_rules",
            calculation_details={"reason": "No applicable commission rules found"},
            hierarchy_commissions=[],
            total_commission=Decimal('0.00'),
            status=CalculationStatus.CALCULATED,
            calculated_at=datetime.utcnow()
        )

# =====================================================
# COMMISSION RULES MANAGEMENT ENDPOINTS
# =====================================================

@app.post("/commission-rules", response_model=CommissionRuleResponse)
async def create_commission_rule(rule_data: CommissionRuleCreate):
    """Create a new commission rule"""
    conn = await get_db_connection()
    try:
        # Validate tier structure for tiered commission
        if rule_data.commission_type == CommissionType.TIERED and not rule_data.tier_structure:
            raise HTTPException(status_code=400, detail="Tier structure is required for tiered commission")
        
        # Insert commission rule
        insert_query = """
        INSERT INTO commission_rules (
            rule_name, description, agent_tier, transaction_type, transaction_channel,
            min_amount, max_amount, territory_id, commission_type, commission_value,
            fixed_amount, percentage_rate, tier_structure, frequency,
            max_commission_per_transaction, max_commission_per_day, max_commission_per_month,
            hierarchy_commission_enabled, hierarchy_commission_rate, hierarchy_max_levels,
            effective_from, effective_until, priority
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
        ) RETURNING *
        """
        
        result = await conn.fetchrow(
            insert_query,
            rule_data.rule_name, rule_data.description, rule_data.agent_tier,
            rule_data.transaction_type, rule_data.transaction_channel,
            rule_data.min_amount, rule_data.max_amount, rule_data.territory_id,
            rule_data.commission_type, rule_data.commission_value,
            rule_data.fixed_amount, rule_data.percentage_rate, 
            json.dumps(rule_data.tier_structure) if rule_data.tier_structure else None,
            rule_data.frequency, rule_data.max_commission_per_transaction,
            rule_data.max_commission_per_day, rule_data.max_commission_per_month,
            rule_data.hierarchy_commission_enabled, rule_data.hierarchy_commission_rate,
            rule_data.hierarchy_max_levels, rule_data.effective_from,
            rule_data.effective_until, rule_data.priority
        )
        
        # Clear rules cache
        redis_conn = await get_redis_connection()
        await redis_conn.delete("commission_rules:*")
        
        return CommissionRuleResponse(
            id=str(result['id']),
            rule_name=result['rule_name'],
            description=result['description'],
            agent_tier=result['agent_tier'],
            transaction_type=result['transaction_type'],
            transaction_channel=result['transaction_channel'],
            min_amount=result['min_amount'],
            max_amount=result['max_amount'],
            territory_id=str(result['territory_id']) if result['territory_id'] else None,
            commission_type=result['commission_type'],
            commission_value=result['commission_value'],
            fixed_amount=result['fixed_amount'],
            percentage_rate=result['percentage_rate'],
            tier_structure=result['tier_structure'],
            frequency=result['frequency'],
            max_commission_per_transaction=result['max_commission_per_transaction'],
            max_commission_per_day=result['max_commission_per_day'],
            max_commission_per_month=result['max_commission_per_month'],
            hierarchy_commission_enabled=result['hierarchy_commission_enabled'],
            hierarchy_commission_rate=result['hierarchy_commission_rate'],
            hierarchy_max_levels=result['hierarchy_max_levels'],
            is_active=result['is_active'],
            effective_from=result['effective_from'],
            effective_until=result['effective_until'],
            priority=result['priority'],
            created_at=result['created_at'],
            updated_at=result['updated_at']
        )
    
    finally:
        await conn.close()

@app.get("/commission-rules", response_model=List[CommissionRuleResponse])
async def list_commission_rules(
    agent_tier: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List commission rules with filtering"""
    conn = await get_db_connection()
    try:
        # Build query with filters
        where_conditions = []
        params = []
        param_count = 0
        
        if agent_tier:
            param_count += 1
            where_conditions.append(f"agent_tier = ${param_count}")
            params.append(agent_tier)
        
        if transaction_type:
            param_count += 1
            where_conditions.append(f"transaction_type = ${param_count}")
            params.append(transaction_type)
        
        if is_active is not None:
            param_count += 1
            where_conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        limit_param = f"${param_count}"
        params.append(limit)
        
        param_count += 1
        offset_param = f"${param_count}"
        params.append(offset)
        
        query = f"""
        SELECT * FROM commission_rules
        {where_clause}
        ORDER BY priority DESC, created_at DESC
        LIMIT {limit_param} OFFSET {offset_param}
        """
        
        results = await conn.fetch(query, *params)
        
        rules = []
        for result in results:
            rules.append(CommissionRuleResponse(
                id=str(result['id']),
                rule_name=result['rule_name'],
                description=result['description'],
                agent_tier=result['agent_tier'],
                transaction_type=result['transaction_type'],
                transaction_channel=result['transaction_channel'],
                min_amount=result['min_amount'],
                max_amount=result['max_amount'],
                territory_id=str(result['territory_id']) if result['territory_id'] else None,
                commission_type=result['commission_type'],
                commission_value=result['commission_value'],
                fixed_amount=result['fixed_amount'],
                percentage_rate=result['percentage_rate'],
                tier_structure=result['tier_structure'],
                frequency=result['frequency'],
                max_commission_per_transaction=result['max_commission_per_transaction'],
                max_commission_per_day=result['max_commission_per_day'],
                max_commission_per_month=result['max_commission_per_month'],
                hierarchy_commission_enabled=result['hierarchy_commission_enabled'],
                hierarchy_commission_rate=result['hierarchy_commission_rate'],
                hierarchy_max_levels=result['hierarchy_max_levels'],
                is_active=result['is_active'],
                effective_from=result['effective_from'],
                effective_until=result['effective_until'],
                priority=result['priority'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            ))
        
        return rules
    
    finally:
        await conn.close()

@app.get("/commission-rules/{rule_id}", response_model=CommissionRuleResponse)
async def get_commission_rule(rule_id: str):
    """Get commission rule by ID"""
    conn = await get_db_connection()
    try:
        result = await conn.fetchrow("SELECT * FROM commission_rules WHERE id = $1", rule_id)
        if not result:
            raise HTTPException(status_code=404, detail="Commission rule not found")
        
        return CommissionRuleResponse(
            id=str(result['id']),
            rule_name=result['rule_name'],
            description=result['description'],
            agent_tier=result['agent_tier'],
            transaction_type=result['transaction_type'],
            transaction_channel=result['transaction_channel'],
            min_amount=result['min_amount'],
            max_amount=result['max_amount'],
            territory_id=str(result['territory_id']) if result['territory_id'] else None,
            commission_type=result['commission_type'],
            commission_value=result['commission_value'],
            fixed_amount=result['fixed_amount'],
            percentage_rate=result['percentage_rate'],
            tier_structure=result['tier_structure'],
            frequency=result['frequency'],
            max_commission_per_transaction=result['max_commission_per_transaction'],
            max_commission_per_day=result['max_commission_per_day'],
            max_commission_per_month=result['max_commission_per_month'],
            hierarchy_commission_enabled=result['hierarchy_commission_enabled'],
            hierarchy_commission_rate=result['hierarchy_commission_rate'],
            hierarchy_max_levels=result['hierarchy_max_levels'],
            is_active=result['is_active'],
            effective_from=result['effective_from'],
            effective_until=result['effective_until'],
            priority=result['priority'],
            created_at=result['created_at'],
            updated_at=result['updated_at']
        )
    
    finally:
        await conn.close()

@app.put("/commission-rules/{rule_id}/toggle")
async def toggle_commission_rule(rule_id: str):
    """Toggle commission rule active status"""
    conn = await get_db_connection()
    try:
        result = await conn.fetchrow(
            "UPDATE commission_rules SET is_active = NOT is_active, updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING is_active",
            rule_id
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Commission rule not found")
        
        # Clear cache
        redis_conn = await get_redis_connection()
        await redis_conn.delete("commission_rules:*")
        
        return {"message": f"Rule {'activated' if result['is_active'] else 'deactivated'} successfully"}
    
    finally:
        await conn.close()

# =====================================================
# COMMISSION CALCULATION ENDPOINTS
# =====================================================

@app.post("/calculate-commission", response_model=CommissionCalculationResult)
async def calculate_commission(request: CommissionCalculationRequest):
    """Calculate commission for a transaction"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        # Check if calculation already exists (unless force recalculation)
        if not request.force_recalculation:
            existing_calc = await conn.fetchrow(
                "SELECT * FROM commission_calculations WHERE transaction_id = $1 AND agent_id = $2",
                request.transaction_data.transaction_id,
                request.transaction_data.agent_id
            )
            
            if existing_calc:
                raise HTTPException(
                    status_code=409, 
                    detail="Commission already calculated for this transaction"
                )
        
        # Initialize calculation engine
        engine = CommissionCalculationEngine(conn, redis_conn)
        
        # Calculate commission
        result = await engine.calculate_commission(request.transaction_data)
        
        return result
    
    finally:
        await conn.close()

@app.get("/commission-calculations/{calculation_id}", response_model=CommissionCalculationResult)
async def get_commission_calculation(calculation_id: str):
    """Get commission calculation by ID"""
    conn = await get_db_connection()
    try:
        # Get primary calculation
        primary_calc = await conn.fetchrow(
            "SELECT * FROM commission_calculations WHERE id = $1",
            calculation_id
        )
        
        if not primary_calc:
            raise HTTPException(status_code=404, detail="Commission calculation not found")
        
        # Get hierarchy calculations
        hierarchy_calcs = await conn.fetch(
            "SELECT * FROM commission_calculations WHERE transaction_id = $1 AND parent_agent_id = $2",
            primary_calc['transaction_id'],
            primary_calc['agent_id']
        )
        
        hierarchy_commissions = []
        for hc in hierarchy_calcs:
            hierarchy_commissions.append({
                'agent_id': hc['agent_id'],
                'hierarchy_level': hc['hierarchy_level'],
                'amount': hc['commission_amount'],
                'rate': hc['commission_rate'],
                'calculation_details': hc['calculation_details']
            })
        
        total_commission = primary_calc['commission_amount'] + sum(hc['amount'] for hc in hierarchy_commissions)
        
        return CommissionCalculationResult(
            calculation_id=str(primary_calc['id']),
            transaction_id=primary_calc['transaction_id'],
            agent_id=primary_calc['agent_id'],
            rule_id=str(primary_calc['rule_id']),
            commission_amount=primary_calc['commission_amount'],
            commission_rate=primary_calc['commission_rate'],
            calculation_method=primary_calc['calculation_method'],
            calculation_details=primary_calc['calculation_details'],
            hierarchy_commissions=hierarchy_commissions,
            total_commission=total_commission,
            status=primary_calc['status'],
            calculated_at=primary_calc['created_at']
        )
    
    finally:
        await conn.close()

@app.get("/agents/{agent_id}/commission-summary", response_model=CommissionSummary)
async def get_agent_commission_summary(
    agent_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    """Get commission summary for an agent"""
    conn = await get_db_connection()
    try:
        # Default to current month if no dates provided
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()
        
        # Get commission summary
        summary_query = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(transaction_amount) as total_volume,
            SUM(commission_amount) as gross_commission,
            SUM(parent_commission_amount) as hierarchy_commission,
            AVG(commission_rate) as avg_commission_rate
        FROM commission_calculations
        WHERE agent_id = $1 
        AND DATE(transaction_date) BETWEEN $2 AND $3
        """
        
        result = await conn.fetchrow(summary_query, agent_id, start_date, end_date)
        
        gross_commission = result['gross_commission'] or Decimal('0.00')
        hierarchy_commission = result['hierarchy_commission'] or Decimal('0.00')
        net_commission = gross_commission - hierarchy_commission
        
        return CommissionSummary(
            agent_id=agent_id,
            period_start=start_date,
            period_end=end_date,
            total_transactions=result['total_transactions'] or 0,
            total_volume=result['total_volume'] or Decimal('0.00'),
            gross_commission=gross_commission,
            hierarchy_commission=hierarchy_commission,
            net_commission=net_commission,
            avg_commission_rate=result['avg_commission_rate'] or Decimal('0.0000')
        )
    
    finally:
        await conn.close()

# =====================================================
# BATCH PROCESSING ENDPOINTS
# =====================================================

@app.post("/calculate-commission/batch")
async def calculate_commission_batch(transactions: List[TransactionData], background_tasks: BackgroundTasks):
    """Calculate commissions for multiple transactions in batch"""
    batch_id = str(uuid.uuid4())
    
    # Add batch processing to background tasks
    background_tasks.add_task(process_commission_batch, batch_id, transactions)
    
    return {
        "batch_id": batch_id,
        "transaction_count": len(transactions),
        "status": "processing",
        "message": "Batch commission calculation started"
    }

async def process_commission_batch(batch_id: str, transactions: List[TransactionData]):
    """Process commission calculations in batch"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        engine = CommissionCalculationEngine(conn, redis_conn)
        
        results = []
        errors = []
        
        for transaction in transactions:
            try:
                result = await engine.calculate_commission(transaction)
                results.append({
                    'transaction_id': transaction.transaction_id,
                    'status': 'success',
                    'calculation_id': result.calculation_id,
                    'commission_amount': float(result.total_commission)
                })
            except Exception as e:
                errors.append({
                    'transaction_id': transaction.transaction_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Store batch results in Redis
        batch_result = {
            'batch_id': batch_id,
            'total_transactions': len(transactions),
            'successful': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        await redis_conn.setex(
            f"commission_batch:{batch_id}",
            86400,  # 24 hours TTL
            json.dumps(batch_result, default=str)
        )
        
        logger.info(f"Batch {batch_id} completed: {len(results)} successful, {len(errors)} failed")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
    finally:
        await conn.close()

@app.get("/calculate-commission/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch processing status"""
    redis_conn = await get_redis_connection()
    
    result = await redis_conn.get(f"commission_batch:{batch_id}")
    if not result:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return json.loads(result)

# =====================================================
# HEALTH CHECK AND METRICS
# =====================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        conn = await get_db_connection()
        await conn.fetchval("SELECT 1")
        await conn.close()
        
        redis_conn = await get_redis_connection()
        await redis_conn.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "redis": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    conn = await get_db_connection()
    try:
        # Get calculation statistics
        calc_stats = await conn.fetchrow("""
        SELECT 
            COUNT(*) as total_calculations,
            COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_calculations,
            SUM(commission_amount) as total_commission,
            AVG(commission_amount) as avg_commission
        FROM commission_calculations
        """)
        
        # Get rule statistics
        rule_stats = await conn.fetchrow("""
        SELECT 
            COUNT(*) as total_rules,
            COUNT(*) FILTER (WHERE is_active = true) as active_rules,
            COUNT(DISTINCT agent_tier) as tiers_covered,
            COUNT(DISTINCT transaction_type) as transaction_types_covered
        FROM commission_rules
        """)
        
        return {
            "calculation_statistics": dict(calc_stats),
            "rule_statistics": dict(rule_stats),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    finally:
        await conn.close()

# =====================================================
# STARTUP AND SHUTDOWN EVENTS
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global db_pool, redis_client
    
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Database pool initialized")
        
        redis_client = redis.from_url(REDIS_URL)
        await redis_client.ping()
        logger.info("Redis client initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global db_pool, redis_client
    
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "commission_engine:app",
        host="0.0.0.0",
        port=8041,
        reload=False,
        log_level="info"
    )
