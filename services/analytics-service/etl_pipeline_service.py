"""
Analytics ETL Pipeline Service
Extract, Transform, Load data for business intelligence and analytics
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import asyncio
import pandas as pd
import json
import logging

import os
# Configuration
app = FastAPI(title="Analytics ETL Pipeline Service")
logger = logging.getLogger(__name__)

# Database connection pools
source_db_pool = None  # Operational database
analytics_db_pool = None  # Analytics database

# Enums
class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class PipelineType(str, Enum):
    SALES_ANALYTICS = "sales_analytics"
    USER_ANALYTICS = "user_analytics"
    INVENTORY_ANALYTICS = "inventory_analytics"
    FINANCIAL_ANALYTICS = "financial_analytics"
    CUSTOMER_BEHAVIOR = "customer_behavior"

# Models
class PipelineRun(BaseModel):
    id: int
    pipeline_type: str
    status: str
    records_processed: int
    records_failed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class AnalyticsQuery(BaseModel):
    metric: str
    start_date: datetime
    end_date: datetime
    group_by: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

# Database initialization
async def init_db():
    global source_db_pool, analytics_db_pool
    
    # Source database (operational)
    source_db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Analytics database
    analytics_db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance_analytics',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create analytics tables
    async with analytics_db_pool.acquire() as conn:
        # Pipeline runs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                pipeline_type VARCHAR(100) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                records_processed INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                error_message TEXT
            )
        ''')
        
        # Sales analytics fact table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_sales (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                order_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                discount_amount DECIMAL(10, 2) DEFAULT 0,
                tax_amount DECIMAL(10, 2) DEFAULT 0,
                shipping_cost DECIMAL(10, 2) DEFAULT 0,
                payment_method VARCHAR(50),
                order_status VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # User analytics fact table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_users (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                user_id INTEGER NOT NULL,
                registration_date DATE,
                last_login_date DATE,
                total_orders INTEGER DEFAULT 0,
                total_spent DECIMAL(10, 2) DEFAULT 0,
                average_order_value DECIMAL(10, 2) DEFAULT 0,
                days_since_last_order INTEGER,
                customer_segment VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Inventory analytics fact table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_inventory (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                product_id INTEGER NOT NULL,
                sku VARCHAR(100) NOT NULL,
                warehouse_id INTEGER NOT NULL,
                quantity_available INTEGER DEFAULT 0,
                quantity_reserved INTEGER DEFAULT 0,
                quantity_sold INTEGER DEFAULT 0,
                reorder_point INTEGER DEFAULT 0,
                days_of_supply INTEGER,
                turnover_rate DECIMAL(10, 4),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Financial analytics fact table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_financial (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                revenue DECIMAL(12, 2) DEFAULT 0,
                cost_of_goods_sold DECIMAL(12, 2) DEFAULT 0,
                gross_profit DECIMAL(12, 2) DEFAULT 0,
                operating_expenses DECIMAL(12, 2) DEFAULT 0,
                net_profit DECIMAL(12, 2) DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                average_order_value DECIMAL(10, 2) DEFAULT 0,
                new_customers INTEGER DEFAULT 0,
                returning_customers INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Customer behavior analytics
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_customer_behavior (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                customer_id INTEGER NOT NULL,
                page_views INTEGER DEFAULT 0,
                session_duration INTEGER DEFAULT 0,
                products_viewed INTEGER DEFAULT 0,
                cart_additions INTEGER DEFAULT 0,
                cart_abandonments INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,
                conversion_rate DECIMAL(5, 4),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales(date)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_users_date ON fact_users(date)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_inventory_date ON fact_inventory(date)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_financial_date ON fact_financial(date)')

# ETL Pipeline Functions

async def extract_sales_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Extract sales data from operational database"""
    async with source_db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                o.id as order_id,
                o.customer_id,
                o.created_at::date as date,
                oi.product_id,
                oi.quantity,
                oi.unit_price,
                oi.total_amount,
                o.discount_amount,
                o.tax_amount,
                o.shipping_cost,
                o.payment_method,
                o.status as order_status
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.created_at >= $1 AND o.created_at < $2
            """,
            start_date, end_date
        )
        
        return pd.DataFrame([dict(row) for row in rows])

async def extract_user_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Extract user analytics data"""
    async with source_db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                u.id as user_id,
                u.created_at::date as registration_date,
                u.last_login_at::date as last_login_date,
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(SUM(o.total_amount), 0) as total_spent,
                COALESCE(AVG(o.total_amount), 0) as average_order_value,
                EXTRACT(DAY FROM NOW() - MAX(o.created_at)) as days_since_last_order
            FROM users u
            LEFT JOIN orders o ON u.id = o.customer_id
            WHERE u.created_at >= $1 AND u.created_at < $2
            GROUP BY u.id, u.created_at, u.last_login_at
            """,
            start_date, end_date
        )
        
        return pd.DataFrame([dict(row) for row in rows])

async def extract_inventory_data(date: datetime) -> pd.DataFrame:
    """Extract inventory analytics data"""
    async with source_db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                i.product_id,
                i.sku,
                i.warehouse_id,
                i.quantity_available,
                i.quantity_reserved,
                i.reorder_point,
                COALESCE(s.quantity_sold, 0) as quantity_sold
            FROM inventory i
            LEFT JOIN (
                SELECT product_id, SUM(quantity) as quantity_sold
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                WHERE o.created_at::date = $1
                GROUP BY product_id
            ) s ON i.product_id = s.product_id
            """,
            date
        )
        
        return pd.DataFrame([dict(row) for row in rows])

async def transform_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Transform sales data"""
    if df.empty:
        return df
    
    # Calculate derived metrics
    df['net_amount'] = df['total_amount'] - df['discount_amount']
    
    # Categorize order sizes
    df['order_size_category'] = pd.cut(
        df['total_amount'],
        bins=[0, 50, 100, 200, float('inf')],
        labels=['Small', 'Medium', 'Large', 'Extra Large']
    )
    
    return df

async def transform_user_data(df: pd.DataFrame) -> pd.DataFrame:
    """Transform user analytics data"""
    if df.empty:
        return df
    
    # Segment customers based on spending
    df['customer_segment'] = pd.cut(
        df['total_spent'],
        bins=[0, 100, 500, 1000, float('inf')],
        labels=['Bronze', 'Silver', 'Gold', 'Platinum']
    )
    
    # Fill null values
    df['days_since_last_order'].fillna(999, inplace=True)
    
    return df

async def transform_inventory_data(df: pd.DataFrame) -> pd.DataFrame:
    """Transform inventory analytics data"""
    if df.empty:
        return df
    
    # Calculate days of supply
    df['days_of_supply'] = df.apply(
        lambda row: row['quantity_available'] / row['quantity_sold'] if row['quantity_sold'] > 0 else 999,
        axis=1
    )
    
    # Calculate turnover rate
    df['turnover_rate'] = df.apply(
        lambda row: row['quantity_sold'] / row['quantity_available'] if row['quantity_available'] > 0 else 0,
        axis=1
    )
    
    return df

async def load_sales_data(df: pd.DataFrame):
    """Load sales data into analytics database"""
    if df.empty:
        return 0
    
    async with analytics_db_pool.acquire() as conn:
        records = df.to_dict('records')
        count = 0
        
        for record in records:
            await conn.execute(
                """
                INSERT INTO fact_sales (
                    date, order_id, customer_id, product_id, quantity,
                    unit_price, total_amount, discount_amount, tax_amount,
                    shipping_cost, payment_method, order_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                record['date'],
                record['order_id'],
                record['customer_id'],
                record['product_id'],
                record['quantity'],
                record['unit_price'],
                record['total_amount'],
                record['discount_amount'],
                record['tax_amount'],
                record['shipping_cost'],
                record['payment_method'],
                record['order_status']
            )
            count += 1
        
        return count

async def load_user_data(df: pd.DataFrame, date: datetime):
    """Load user analytics data"""
    if df.empty:
        return 0
    
    async with analytics_db_pool.acquire() as conn:
        records = df.to_dict('records')
        count = 0
        
        for record in records:
            await conn.execute(
                """
                INSERT INTO fact_users (
                    date, user_id, registration_date, last_login_date,
                    total_orders, total_spent, average_order_value,
                    days_since_last_order, customer_segment
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                date,
                record['user_id'],
                record['registration_date'],
                record['last_login_date'],
                record['total_orders'],
                record['total_spent'],
                record['average_order_value'],
                record['days_since_last_order'],
                record['customer_segment']
            )
            count += 1
        
        return count

async def load_inventory_data(df: pd.DataFrame, date: datetime):
    """Load inventory analytics data"""
    if df.empty:
        return 0
    
    async with analytics_db_pool.acquire() as conn:
        records = df.to_dict('records')
        count = 0
        
        for record in records:
            await conn.execute(
                """
                INSERT INTO fact_inventory (
                    date, product_id, sku, warehouse_id,
                    quantity_available, quantity_reserved, quantity_sold,
                    reorder_point, days_of_supply, turnover_rate
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                date,
                record['product_id'],
                record['sku'],
                record['warehouse_id'],
                record['quantity_available'],
                record['quantity_reserved'],
                record['quantity_sold'],
                record['reorder_point'],
                record['days_of_supply'],
                record['turnover_rate']
            )
            count += 1
        
        return count

async def run_sales_analytics_pipeline(start_date: datetime, end_date: datetime) -> int:
    """Run sales analytics ETL pipeline"""
    logger.info(f"Running sales analytics pipeline: {start_date} to {end_date}")
    
    # Extract
    df = await extract_sales_data(start_date, end_date)
    logger.info(f"Extracted {len(df)} sales records")
    
    # Transform
    df = await transform_sales_data(df)
    logger.info(f"Transformed {len(df)} sales records")
    
    # Load
    count = await load_sales_data(df)
    logger.info(f"Loaded {count} sales records")
    
    return count

async def run_user_analytics_pipeline(start_date: datetime, end_date: datetime) -> int:
    """Run user analytics ETL pipeline"""
    logger.info(f"Running user analytics pipeline: {start_date} to {end_date}")
    
    # Extract
    df = await extract_user_data(start_date, end_date)
    logger.info(f"Extracted {len(df)} user records")
    
    # Transform
    df = await transform_user_data(df)
    logger.info(f"Transformed {len(df)} user records")
    
    # Load
    count = await load_user_data(df, end_date)
    logger.info(f"Loaded {count} user records")
    
    return count

async def run_inventory_analytics_pipeline(date: datetime) -> int:
    """Run inventory analytics ETL pipeline"""
    logger.info(f"Running inventory analytics pipeline for {date}")
    
    # Extract
    df = await extract_inventory_data(date)
    logger.info(f"Extracted {len(df)} inventory records")
    
    # Transform
    df = await transform_inventory_data(df)
    logger.info(f"Transformed {len(df)} inventory records")
    
    # Load
    count = await load_inventory_data(df, date)
    logger.info(f"Loaded {count} inventory records")
    
    return count

async def scheduled_pipeline_runner():
    """Background task to run pipelines on schedule"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            
            now = datetime.utcnow()
            today = now.date()
            yesterday = today - timedelta(days=1)
            
            # Run daily pipelines
            logger.info("Starting scheduled pipeline runs")
            
            # Sales analytics
            await run_sales_analytics_pipeline(
                datetime.combine(yesterday, datetime.min.time()),
                datetime.combine(today, datetime.min.time())
            )
            
            # User analytics
            await run_user_analytics_pipeline(
                datetime.combine(yesterday, datetime.min.time()),
                datetime.combine(today, datetime.min.time())
            )
            
            # Inventory analytics
            await run_inventory_analytics_pipeline(yesterday)
            
            logger.info("Scheduled pipeline runs completed")
            
        except Exception as e:
            logger.error(f"Error in scheduled pipeline runner: {e}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()
    # Start background pipeline runner
    asyncio.create_task(scheduled_pipeline_runner())

@app.on_event("shutdown")
async def shutdown():
    if source_db_pool:
        await source_db_pool.close()
    if analytics_db_pool:
        await analytics_db_pool.close()

@app.post("/pipelines/run/{pipeline_type}")
async def run_pipeline(
    pipeline_type: PipelineType,
    start_date: datetime,
    end_date: datetime,
    background_tasks: BackgroundTasks
):
    """Trigger pipeline run"""
    async with analytics_db_pool.acquire() as conn:
        run_id = await conn.fetchval(
            """
            INSERT INTO pipeline_runs (pipeline_type, status)
            VALUES ($1, 'running')
            RETURNING id
            """,
            pipeline_type.value
        )
        
        try:
            if pipeline_type == PipelineType.SALES_ANALYTICS:
                count = await run_sales_analytics_pipeline(start_date, end_date)
            elif pipeline_type == PipelineType.USER_ANALYTICS:
                count = await run_user_analytics_pipeline(start_date, end_date)
            elif pipeline_type == PipelineType.INVENTORY_ANALYTICS:
                count = await run_inventory_analytics_pipeline(start_date.date())
            else:
                count = 0
            
            # Update run status
            await conn.execute(
                """
                UPDATE pipeline_runs
                SET status = 'completed',
                    records_processed = $1,
                    completed_at = NOW()
                WHERE id = $2
                """,
                count, run_id
            )
            
            return {
                "run_id": run_id,
                "status": "completed",
                "records_processed": count
            }
            
        except Exception as e:
            # Update run status with error
            await conn.execute(
                """
                UPDATE pipeline_runs
                SET status = 'failed',
                    error_message = $1,
                    completed_at = NOW()
                WHERE id = $2
                """,
                str(e), run_id
            )
            
            raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

@app.get("/pipelines/runs")
async def get_pipeline_runs(limit: int = 50):
    """Get pipeline run history"""
    async with analytics_db_pool.acquire() as conn:
        runs = await conn.fetch(
            """
            SELECT * FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit
        )
        
        return [PipelineRun(**dict(run)) for run in runs]

@app.get("/analytics/sales")
async def get_sales_analytics(start_date: datetime, end_date: datetime):
    """Get sales analytics"""
    async with analytics_db_pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT 
                date,
                COUNT(DISTINCT order_id) as total_orders,
                SUM(quantity) as total_items_sold,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as average_order_value
            FROM fact_sales
            WHERE date >= $1 AND date <= $2
            GROUP BY date
            ORDER BY date
            """,
            start_date.date(), end_date.date()
        )
        
        return [dict(row) for row in results]

@app.get("/analytics/customers")
async def get_customer_analytics(date: datetime):
    """Get customer analytics"""
    async with analytics_db_pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT 
                customer_segment,
                COUNT(*) as customer_count,
                AVG(total_spent) as avg_lifetime_value,
                AVG(total_orders) as avg_orders_per_customer
            FROM fact_users
            WHERE date = $1
            GROUP BY customer_segment
            ORDER BY customer_segment
            """,
            date.date()
        )
        
        return [dict(row) for row in results]

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "analytics_etl",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)

