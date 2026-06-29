"""
Product Catalog Service
Advanced product catalog with search, filtering, categorization, and recommendations
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
import json
import logging
from decimal import Decimal

import os
# Configuration
app = FastAPI(title="Product Catalog Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Enums
class SortBy(str, Enum):
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    NEWEST = "newest"
    POPULAR = "popular"
    RATING = "rating"

class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"

# Models
class Category(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    product_count: int = 0
    is_active: bool = True

class ProductVariant(BaseModel):
    id: int
    product_id: int
    sku: str
    name: str
    attributes: Dict[str, Any]  # e.g., {"color": "red", "size": "L"}
    price: float
    compare_at_price: Optional[float] = None
    stock_quantity: int
    weight: Optional[float] = None
    dimensions: Optional[Dict[str, float]] = None

class ProductImage(BaseModel):
    id: int
    product_id: int
    url: str
    alt_text: Optional[str] = None
    position: int
    is_primary: bool = False

class ProductReview(BaseModel):
    id: int
    product_id: int
    customer_id: int
    customer_name: str
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    verified_purchase: bool = False
    helpful_count: int = 0
    created_at: datetime

class Product(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_id: int
    category_name: str
    brand: Optional[str] = None
    sku: str
    base_price: float
    compare_at_price: Optional[float] = None
    currency: str = "USD"
    status: ProductStatus
    stock_quantity: int
    low_stock_threshold: int = 10
    images: List[ProductImage] = []
    variants: List[ProductVariant] = []
    tags: List[str] = []
    attributes: Dict[str, Any] = {}
    rating_average: float = 0.0
    rating_count: int = 0
    review_count: int = 0
    view_count: int = 0
    purchase_count: int = 0
    is_featured: bool = False
    is_new: bool = False
    is_on_sale: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ProductListResponse(BaseModel):
    products: List[Product]
    total: int
    page: int
    page_size: int
    total_pages: int
    filters_applied: Dict[str, Any]

class SearchFilters(BaseModel):
    query: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    tags: Optional[List[str]] = None
    in_stock: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_on_sale: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

# Database initialization
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        # Categories table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS product_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                slug VARCHAR(200) UNIQUE NOT NULL,
                parent_id INTEGER REFERENCES product_categories(id),
                description TEXT,
                image_url VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Products table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(300) NOT NULL,
                slug VARCHAR(300) UNIQUE NOT NULL,
                description TEXT,
                short_description TEXT,
                category_id INTEGER REFERENCES product_categories(id),
                brand VARCHAR(100),
                sku VARCHAR(100) UNIQUE NOT NULL,
                base_price DECIMAL(10,2) NOT NULL,
                compare_at_price DECIMAL(10,2),
                currency VARCHAR(3) DEFAULT 'USD',
                status VARCHAR(50) DEFAULT 'active',
                stock_quantity INTEGER DEFAULT 0,
                low_stock_threshold INTEGER DEFAULT 10,
                tags JSONB DEFAULT '[]',
                attributes JSONB DEFAULT '{}',
                rating_average DECIMAL(3,2) DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                review_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                purchase_count INTEGER DEFAULT 0,
                is_featured BOOLEAN DEFAULT FALSE,
                is_new BOOLEAN DEFAULT FALSE,
                is_on_sale BOOLEAN DEFAULT FALSE,
                meta_title VARCHAR(200),
                meta_description TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Product variants table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS product_variants (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                sku VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                attributes JSONB NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                compare_at_price DECIMAL(10,2),
                stock_quantity INTEGER DEFAULT 0,
                weight DECIMAL(10,3),
                dimensions JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Product images table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS product_images (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                url VARCHAR(500) NOT NULL,
                alt_text VARCHAR(200),
                position INTEGER DEFAULT 0,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Product reviews table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS product_reviews (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                customer_id INTEGER NOT NULL,
                customer_name VARCHAR(200) NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                title VARCHAR(200),
                comment TEXT,
                verified_purchase BOOLEAN DEFAULT FALSE,
                helpful_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Create indexes for performance
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_featured ON products(is_featured)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_price ON products(base_price)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating_average)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_products_created ON products(created_at)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_product_reviews_product ON product_reviews(product_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_product_variants_product ON product_variants(product_id)')

# Helper functions
async def build_search_query(filters: SearchFilters) -> tuple:
    """Build SQL query based on search filters"""
    conditions = ["p.status = 'active'"]
    params = []
    param_count = 1
    
    if filters.query:
        conditions.append(f"(p.name ILIKE ${param_count} OR p.description ILIKE ${param_count} OR p.tags::text ILIKE ${param_count})")
        params.append(f"%{filters.query}%")
        param_count += 1
    
    if filters.category_id:
        conditions.append(f"p.category_id = ${param_count}")
        params.append(filters.category_id)
        param_count += 1
    
    if filters.brand:
        conditions.append(f"p.brand = ${param_count}")
        params.append(filters.brand)
        param_count += 1
    
    if filters.min_price is not None:
        conditions.append(f"p.base_price >= ${param_count}")
        params.append(filters.min_price)
        param_count += 1
    
    if filters.max_price is not None:
        conditions.append(f"p.base_price <= ${param_count}")
        params.append(filters.max_price)
        param_count += 1
    
    if filters.min_rating is not None:
        conditions.append(f"p.rating_average >= ${param_count}")
        params.append(filters.min_rating)
        param_count += 1
    
    if filters.in_stock:
        conditions.append("p.stock_quantity > 0")
    
    if filters.is_featured is not None:
        conditions.append(f"p.is_featured = ${param_count}")
        params.append(filters.is_featured)
        param_count += 1
    
    if filters.is_on_sale is not None:
        conditions.append(f"p.is_on_sale = ${param_count}")
        params.append(filters.is_on_sale)
        param_count += 1
    
    if filters.tags:
        conditions.append(f"p.tags ?| ${param_count}")
        params.append(filters.tags)
        param_count += 1
    
    where_clause = " AND ".join(conditions)
    return where_clause, params

async def get_product_images(product_id: int) -> List[ProductImage]:
    """Get all images for a product"""
    async with db_pool.acquire() as conn:
        images = await conn.fetch(
            """
            SELECT * FROM product_images
            WHERE product_id = $1
            ORDER BY position, id
            """,
            product_id
        )
        return [ProductImage(**dict(img)) for img in images]

async def get_product_variants(product_id: int) -> List[ProductVariant]:
    """Get all variants for a product"""
    async with db_pool.acquire() as conn:
        variants = await conn.fetch(
            """
            SELECT * FROM product_variants
            WHERE product_id = $1
            ORDER BY id
            """,
            product_id
        )
        return [ProductVariant(**dict(var)) for var in variants]

async def increment_view_count(product_id: int):
    """Increment product view count"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE products SET view_count = view_count + 1 WHERE id = $1",
            product_id
        )

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.get("/categories", response_model=List[Category])
async def get_categories(
    parent_id: Optional[int] = None,
    active_only: bool = True
):
    """Get product categories"""
    async with db_pool.acquire() as conn:
        if parent_id is not None:
            query = """
                SELECT c.*, COUNT(p.id) as product_count
                FROM product_categories c
                LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
                WHERE c.parent_id = $1
            """
            params = [parent_id]
        else:
            query = """
                SELECT c.*, COUNT(p.id) as product_count
                FROM product_categories c
                LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
                WHERE c.parent_id IS NULL
            """
            params = []
        
        if active_only:
            query += " AND c.is_active = TRUE"
        
        query += " GROUP BY c.id ORDER BY c.position, c.name"
        
        categories = await conn.fetch(query, *params)
        return [Category(**dict(cat)) for cat in categories]

@app.get("/categories/{category_id}", response_model=Category)
async def get_category(category_id: int):
    """Get category details"""
    async with db_pool.acquire() as conn:
        category = await conn.fetchrow(
            """
            SELECT c.*, COUNT(p.id) as product_count
            FROM product_categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
            WHERE c.id = $1
            GROUP BY c.id
            """,
            category_id
        )
        
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        
        return Category(**dict(category))

@app.get("/products", response_model=ProductListResponse)
async def search_products(
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    in_stock: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    is_on_sale: Optional[bool] = None,
    sort_by: SortBy = SortBy.NEWEST,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Search and filter products"""
    filters = SearchFilters(
        query=query,
        category_id=category_id,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
        is_featured=is_featured,
        is_on_sale=is_on_sale
    )
    
    where_clause, params = await build_search_query(filters)
    
    # Build sort clause
    sort_clauses = {
        SortBy.PRICE_ASC: "p.base_price ASC",
        SortBy.PRICE_DESC: "p.base_price DESC",
        SortBy.NAME_ASC: "p.name ASC",
        SortBy.NAME_DESC: "p.name DESC",
        SortBy.NEWEST: "p.created_at DESC",
        SortBy.POPULAR: "p.purchase_count DESC",
        SortBy.RATING: "p.rating_average DESC"
    }
    sort_clause = sort_clauses.get(sort_by, "p.created_at DESC")
    
    offset = (page - 1) * page_size
    
    async with db_pool.acquire() as conn:
        # Get total count
        count_query = f"""
            SELECT COUNT(*) FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            WHERE {where_clause}
        """
        total = await conn.fetchval(count_query, *params)
        
        # Get products
        products_query = f"""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            WHERE {where_clause}
            ORDER BY {sort_clause}
            LIMIT {page_size} OFFSET {offset}
        """
        
        products = await conn.fetch(products_query, *params)
        
        # Build product list with images and variants
        product_list = []
        for prod in products:
            product_dict = dict(prod)
            product_dict['images'] = await get_product_images(product_dict['id'])
            product_dict['variants'] = await get_product_variants(product_dict['id'])
            product_list.append(Product(**product_dict))
        
        total_pages = (total + page_size - 1) // page_size
        
        return ProductListResponse(
            products=product_list,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            filters_applied=filters.dict(exclude_none=True)
        )

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    """Get product details"""
    async with db_pool.acquire() as conn:
        product = await conn.fetchrow(
            """
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            WHERE p.id = $1
            """,
            product_id
        )
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Increment view count
        await increment_view_count(product_id)
        
        # Get images and variants
        product_dict = dict(product)
        product_dict['images'] = await get_product_images(product_id)
        product_dict['variants'] = await get_product_variants(product_id)
        
        return Product(**product_dict)

@app.get("/products/{product_id}/reviews", response_model=List[ProductReview])
async def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """Get product reviews"""
    offset = (page - 1) * page_size
    
    async with db_pool.acquire() as conn:
        reviews = await conn.fetch(
            """
            SELECT * FROM product_reviews
            WHERE product_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            product_id, page_size, offset
        )
        
        return [ProductReview(**dict(review)) for review in reviews]

@app.get("/products/{product_id}/related", response_model=List[Product])
async def get_related_products(product_id: int, limit: int = Query(4, ge=1, le=20)):
    """Get related products based on category and tags"""
    async with db_pool.acquire() as conn:
        # Get current product
        current = await conn.fetchrow(
            "SELECT category_id, tags FROM products WHERE id = $1",
            product_id
        )
        
        if not current:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Find related products
        related = await conn.fetch(
            """
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            WHERE p.id != $1
            AND p.status = 'active'
            AND (p.category_id = $2 OR p.tags && $3)
            ORDER BY 
                CASE WHEN p.category_id = $2 THEN 1 ELSE 2 END,
                p.rating_average DESC,
                p.purchase_count DESC
            LIMIT $4
            """,
            product_id, current['category_id'], current['tags'], limit
        )
        
        # Build product list
        product_list = []
        for prod in related:
            product_dict = dict(prod)
            product_dict['images'] = await get_product_images(product_dict['id'])
            product_dict['variants'] = await get_product_variants(product_dict['id'])
            product_list.append(Product(**product_dict))
        
        return product_list

@app.get("/brands")
async def get_brands():
    """Get all brands with product counts"""
    async with db_pool.acquire() as conn:
        brands = await conn.fetch(
            """
            SELECT brand, COUNT(*) as product_count
            FROM products
            WHERE status = 'active' AND brand IS NOT NULL
            GROUP BY brand
            ORDER BY brand
            """
        )
        
        return [{"name": b['brand'], "product_count": b['product_count']} for b in brands]

@app.get("/featured", response_model=List[Product])
async def get_featured_products(limit: int = Query(10, ge=1, le=50)):
    """Get featured products"""
    async with db_pool.acquire() as conn:
        products = await conn.fetch(
            """
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            WHERE p.is_featured = TRUE AND p.status = 'active'
            ORDER BY p.purchase_count DESC, p.rating_average DESC
            LIMIT $1
            """,
            limit
        )
        
        product_list = []
        for prod in products:
            product_dict = dict(prod)
            product_dict['images'] = await get_product_images(product_dict['id'])
            product_dict['variants'] = await get_product_variants(product_dict['id'])
            product_list.append(Product(**product_dict))
        
        return product_list

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "product_catalog",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)

