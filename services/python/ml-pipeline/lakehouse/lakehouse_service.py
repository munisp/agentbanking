#!/usr/bin/env python3
"""
Unified Lakehouse API Service — FastAPI at :8156

This is the single Lakehouse gateway that all microservices (Go, Rust, Python, TypeScript)
call for data ingestion, querying, and catalog operations.

Architecture:
    Go/Rust/Python services ──► POST /v1/ingest  ──► Bronze layer (raw Parquet)
    TypeScript tRPC proxy   ──► POST /v1/query   ──► DataFusion SQL engine
    All services            ──► GET  /v1/catalog ──► Schema registry + metadata

Data Flow (Medallion Architecture):
    Ingest ──► Bronze (raw, append-only) ──► Silver (cleaned, deduped) ──► Gold (aggregated)

Endpoints:
    POST /v1/ingest          — Ingest records into Bronze layer
    POST /v1/query           — Execute SQL query via DataFusion/DuckDB
    GET  /v1/catalog         — List all tables and schemas
    GET  /v1/catalog/{table} — Get table schema, stats, and versions
    POST /v1/etl/promote     — Run Bronze→Silver→Gold ETL for a table
    GET  /v1/quality/{table} — Get data quality report for a table
    GET  /health             — Service health check

Usage:
    python -m lakehouse.lakehouse_service
    # or
    uvicorn lakehouse.lakehouse_service:app --host 0.0.0.0 --port 8156
"""

import os
import json
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Try DuckDB for SQL queries (lighter than DataFusion, no Rust build needed)
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

LAKEHOUSE_ROOT = Path(os.getenv("LAKEHOUSE_ROOT",
    str(Path(__file__).parent.parent / "models" / "lakehouse")))
LAKEHOUSE_ROOT.mkdir(parents=True, exist_ok=True)

# Medallion layer paths
BRONZE_PATH = LAKEHOUSE_ROOT / "bronze"
SILVER_PATH = LAKEHOUSE_ROOT / "silver"
GOLD_PATH = LAKEHOUSE_ROOT / "gold"
CATALOG_PATH = LAKEHOUSE_ROOT / "_catalog"
QUALITY_PATH = LAKEHOUSE_ROOT / "_quality"

for p in [BRONZE_PATH, SILVER_PATH, GOLD_PATH, CATALOG_PATH, QUALITY_PATH]:
    p.mkdir(parents=True, exist_ok=True)


# ======================== Pydantic Models ========================

class IngestRequest(BaseModel):
    table: str = Field(..., description="Target table name (e.g., 'fraud-detection_events')")
    data: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(..., description="Record(s) to ingest")
    source: Optional[str] = Field(None, description="Source service name")

class IngestResponse(BaseModel):
    status: str
    table: str
    records_ingested: int
    layer: str
    version: int
    partition: str

class QueryRequest(BaseModel):
    sql: str = Field(..., description="SQL query to execute")
    layer: str = Field("gold", description="Which layer to query: bronze, silver, gold")
    limit: int = Field(1000, description="Max rows to return")

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float

class ETLPromoteRequest(BaseModel):
    table: str = Field(..., description="Table to promote")
    source_layer: str = Field("bronze", description="Source layer")
    target_layer: str = Field("silver", description="Target layer")

class TableSchema(BaseModel):
    table_name: str
    layer: str
    columns: Dict[str, str]
    row_count: int
    size_bytes: int
    versions: int
    last_updated: str
    partitions: List[str]

class QualityReport(BaseModel):
    table_name: str
    layer: str
    timestamp: str
    total_rows: int
    null_counts: Dict[str, int]
    duplicate_rows: int
    numeric_ranges: Dict[str, Dict[str, float]]
    categorical_cardinality: Dict[str, int]
    quality_score: float
    issues: List[str]


# ======================== Data Quality Engine ========================

class DataQualityEngine:
    """Validates data quality on ingestion and reports issues"""

    # Schema definitions for known table types
    KNOWN_SCHEMAS = {
        "transactions": {
            "required_columns": ["transaction_id", "amount", "timestamp"],
            "numeric_ranges": {"amount": (0, 100_000_000)},  # 0 to 100M NGN
            "not_null": ["transaction_id", "amount"],
        },
        "fraud": {
            "required_columns": ["event_id", "score"],
            "numeric_ranges": {"score": (0.0, 1.0)},
            "not_null": ["event_id"],
        },
        "credit": {
            "required_columns": ["customer_id", "score"],
            "numeric_ranges": {"score": (0, 1000)},
            "not_null": ["customer_id"],
        },
        "agents": {
            "required_columns": ["agent_id"],
            "not_null": ["agent_id"],
        },
    }

    def validate_record(self, table: str, record: Dict[str, Any]) -> List[str]:
        """Validate a single record against schema"""
        issues = []
        schema = self._get_schema(table)
        if not schema:
            return issues  # No schema → skip validation

        # Check required columns
        for col in schema.get("required_columns", []):
            if col not in record:
                issues.append(f"missing_column:{col}")

        # Check not-null constraints
        for col in schema.get("not_null", []):
            if col in record and record[col] is None:
                issues.append(f"null_value:{col}")

        # Check numeric ranges
        for col, (min_val, max_val) in schema.get("numeric_ranges", {}).items():
            if col in record and record[col] is not None:
                try:
                    val = float(record[col])
                    if val < min_val or val > max_val:
                        issues.append(f"out_of_range:{col}={val} (expected {min_val}-{max_val})")
                except (ValueError, TypeError):
                    issues.append(f"invalid_numeric:{col}={record[col]}")

        return issues

    def generate_quality_report(self, table: str, layer: str, df: pd.DataFrame) -> QualityReport:
        """Generate a comprehensive quality report for a table"""
        issues = []
        null_counts = {}
        numeric_ranges = {}
        categorical_cardinality = {}

        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            null_counts[col] = null_count
            if null_count > len(df) * 0.5:
                issues.append(f"High null rate in {col}: {null_count}/{len(df)} ({null_count/len(df)*100:.1f}%)")

            if pd.api.types.is_numeric_dtype(df[col]):
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    numeric_ranges[col] = {
                        "min": float(non_null.min()),
                        "max": float(non_null.max()),
                        "mean": float(non_null.mean()),
                        "std": float(non_null.std()) if len(non_null) > 1 else 0.0,
                    }
            elif pd.api.types.is_string_dtype(df[col]):
                cardinality = int(df[col].nunique())
                categorical_cardinality[col] = cardinality

        # Check duplicates
        duplicate_rows = int(df.duplicated().sum())
        if duplicate_rows > 0:
            issues.append(f"Found {duplicate_rows} duplicate rows")

        # Quality score (0-100)
        total_cells = len(df) * len(df.columns)
        total_nulls = sum(null_counts.values())
        null_ratio = total_nulls / max(total_cells, 1)
        dup_ratio = duplicate_rows / max(len(df), 1)
        quality_score = max(0, 100 - (null_ratio * 50) - (dup_ratio * 30) - (len(issues) * 5))

        return QualityReport(
            table_name=table,
            layer=layer,
            timestamp=datetime.now().isoformat(),
            total_rows=len(df),
            null_counts=null_counts,
            duplicate_rows=duplicate_rows,
            numeric_ranges=numeric_ranges,
            categorical_cardinality=categorical_cardinality,
            quality_score=round(quality_score, 2),
            issues=issues,
        )

    def _get_schema(self, table: str) -> Optional[Dict]:
        for key, schema in self.KNOWN_SCHEMAS.items():
            if key in table.lower():
                return schema
        return None


# ======================== Catalog Manager ========================

class CatalogManager:
    """Manages the data catalog / schema registry"""

    def __init__(self, catalog_path: Path = CATALOG_PATH):
        self.catalog_path = catalog_path
        self.catalog_path.mkdir(parents=True, exist_ok=True)

    def register_table(self, table_name: str, layer: str, columns: Dict[str, str],
                       row_count: int, size_bytes: int, version: int):
        """Register or update a table in the catalog"""
        table_key = f"{layer}__{table_name}"
        entry = {
            "table_name": table_name,
            "layer": layer,
            "columns": columns,
            "row_count": row_count,
            "size_bytes": size_bytes,
            "version": version,
            "last_updated": datetime.now().isoformat(),
            "registered_at": datetime.now().isoformat(),
        }

        # Load existing entry if any
        entry_path = self.catalog_path / f"{table_key}.json"
        if entry_path.exists():
            with open(entry_path) as f:
                existing = json.load(f)
            entry["registered_at"] = existing.get("registered_at", entry["registered_at"])
            entry["versions"] = existing.get("versions", []) + [version]
        else:
            entry["versions"] = [version]

        with open(entry_path, "w") as f:
            json.dump(entry, f, indent=2)

    def list_tables(self, layer: Optional[str] = None) -> List[Dict]:
        """List all registered tables"""
        tables = []
        for f in sorted(self.catalog_path.glob("*.json")):
            with open(f) as fp:
                entry = json.load(fp)
            if layer is None or entry.get("layer") == layer:
                tables.append(entry)
        return tables

    def get_table(self, table_name: str, layer: str = None) -> Optional[Dict]:
        """Get a specific table's catalog entry"""
        for f in self.catalog_path.glob("*.json"):
            with open(f) as fp:
                entry = json.load(fp)
            if entry["table_name"] == table_name:
                if layer is None or entry.get("layer") == layer:
                    return entry
        return None


# ======================== ETL Pipeline (Bronze → Silver → Gold) ========================

class MedallionETL:
    """Bronze → Silver → Gold ETL pipeline"""

    def __init__(self):
        self.quality_engine = DataQualityEngine()
        self.catalog = CatalogManager()

    def ingest_to_bronze(self, table: str, records: List[Dict[str, Any]], source: str = None) -> Dict:
        """Ingest raw records into Bronze layer (append-only)"""
        table_dir = BRONZE_PATH / table
        table_dir.mkdir(parents=True, exist_ok=True)

        # Add ingestion metadata
        ingestion_ts = datetime.now().isoformat()
        for r in records:
            r["_ingested_at"] = ingestion_ts
            r["_source"] = source or "unknown"
            r["_record_id"] = hashlib.md5(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:16]

        # Write as partitioned Parquet (by date)
        df = pd.DataFrame(records)
        partition = datetime.now().strftime("%Y-%m-%d")
        version = int(time.time())

        partition_dir = table_dir / f"date={partition}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = partition_dir / f"v{version}.parquet"
        df.to_parquet(parquet_path, index=False)

        # Register in catalog
        columns = {col: str(dtype) for col, dtype in df.dtypes.items()}
        self.catalog.register_table(
            table_name=table, layer="bronze", columns=columns,
            row_count=len(df), size_bytes=parquet_path.stat().st_size, version=version,
        )

        logger.info(f"[Bronze] Ingested {len(records)} records to {table} (partition={partition})")

        return {
            "layer": "bronze",
            "table": table,
            "records": len(records),
            "version": version,
            "partition": partition,
            "path": str(parquet_path),
        }

    def promote_to_silver(self, table: str) -> Dict:
        """Promote Bronze → Silver (deduplicate, clean nulls, enforce types)"""
        bronze_dir = BRONZE_PATH / table
        if not bronze_dir.exists():
            raise FileNotFoundError(f"No bronze data for table: {table}")

        # Read all bronze partitions
        parquet_files = list(bronze_dir.rglob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files in bronze/{table}")

        dfs = [pd.read_parquet(f) for f in parquet_files]
        df = pd.concat(dfs, ignore_index=True)

        original_count = len(df)

        # Deduplication
        if "_record_id" in df.columns:
            df = df.drop_duplicates(subset=["_record_id"], keep="last")

        # Drop rows with all-null business columns (keep metadata columns)
        biz_cols = [c for c in df.columns if not c.startswith("_")]
        if biz_cols:
            df = df.dropna(subset=biz_cols, how="all")

        # Type coercion for known numeric columns
        for col in df.columns:
            if any(kw in col.lower() for kw in ["amount", "fee", "score", "count", "rate", "distance"]):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        deduped_count = len(df)

        # Write Silver
        silver_dir = SILVER_PATH / table
        silver_dir.mkdir(parents=True, exist_ok=True)
        version = int(time.time())
        silver_path = silver_dir / f"v{version}.parquet"
        df.to_parquet(silver_path, index=False)

        # Register
        columns = {col: str(dtype) for col, dtype in df.dtypes.items()}
        self.catalog.register_table(
            table_name=table, layer="silver", columns=columns,
            row_count=len(df), size_bytes=silver_path.stat().st_size, version=version,
        )

        logger.info(f"[Silver] Promoted {table}: {original_count} → {deduped_count} rows "
                     f"(removed {original_count - deduped_count} duplicates/nulls)")

        return {
            "layer": "silver",
            "table": table,
            "original_rows": original_count,
            "silver_rows": deduped_count,
            "removed": original_count - deduped_count,
            "version": version,
        }

    def promote_to_gold(self, table: str) -> Dict:
        """Promote Silver → Gold (aggregate metrics, build materialized views)"""
        silver_dir = SILVER_PATH / table
        if not silver_dir.exists():
            raise FileNotFoundError(f"No silver data for table: {table}")

        parquet_files = list(silver_dir.glob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files in silver/{table}")

        # Read latest silver version
        latest = sorted(parquet_files)[-1]
        df = pd.read_parquet(latest)

        gold_tables = {}

        # Generate aggregation based on table type
        if "transaction" in table.lower() or "event" in table.lower():
            gold_tables.update(self._aggregate_events(table, df))
        elif "credit" in table.lower() or "score" in table.lower():
            gold_tables.update(self._aggregate_scores(table, df))
        else:
            gold_tables.update(self._aggregate_generic(table, df))

        # Write all gold tables
        version = int(time.time())
        results = {}
        for gold_name, gold_df in gold_tables.items():
            gold_dir = GOLD_PATH / gold_name
            gold_dir.mkdir(parents=True, exist_ok=True)
            gold_path = gold_dir / f"v{version}.parquet"
            gold_df.to_parquet(gold_path, index=False)

            columns = {col: str(dtype) for col, dtype in gold_df.dtypes.items()}
            self.catalog.register_table(
                table_name=gold_name, layer="gold", columns=columns,
                row_count=len(gold_df), size_bytes=gold_path.stat().st_size, version=version,
            )
            results[gold_name] = len(gold_df)

        logger.info(f"[Gold] Promoted {table} → {len(gold_tables)} gold tables")

        return {
            "layer": "gold",
            "source_table": table,
            "gold_tables": results,
            "version": version,
        }

    def _aggregate_events(self, table: str, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Aggregate event data into gold-layer summary tables"""
        gold = {}

        # Daily summary
        if "_ingested_at" in df.columns:
            df["_date"] = pd.to_datetime(df["_ingested_at"]).dt.date.astype(str)
        else:
            df["_date"] = datetime.now().strftime("%Y-%m-%d")

        daily = df.groupby("_date").agg(
            record_count=("_date", "count"),
        ).reset_index()

        # Add numeric aggregations for any amount-like columns
        for col in df.columns:
            if any(kw in col.lower() for kw in ["amount", "fee", "score", "revenue"]):
                numeric_col = pd.to_numeric(df[col], errors="coerce")
                daily_agg = numeric_col.groupby(df["_date"]).agg(["sum", "mean", "min", "max"])
                daily_agg.columns = [f"{col}_{stat}" for stat in ["sum", "mean", "min", "max"]]
                daily = daily.merge(daily_agg, left_on="_date", right_index=True, how="left")

        gold[f"{table}_daily_summary"] = daily

        # Source distribution
        if "_source" in df.columns:
            source_dist = df.groupby("_source").size().reset_index(name="count")
            gold[f"{table}_by_source"] = source_dist

        return gold

    def _aggregate_scores(self, table: str, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Aggregate scoring data"""
        gold = {}

        score_cols = [c for c in df.columns if "score" in c.lower()]
        if score_cols:
            score_col = score_cols[0]
            numeric_scores = pd.to_numeric(df[score_col], errors="coerce").dropna()
            if len(numeric_scores) > 0:
                buckets = pd.cut(numeric_scores, bins=10)
                dist = buckets.value_counts().sort_index().reset_index()
                dist.columns = ["bucket", "count"]
                dist["bucket"] = dist["bucket"].astype(str)
                gold[f"{table}_score_distribution"] = dist

        # Overall stats
        stats = {"table": [table], "total_records": [len(df)]}
        for col in score_cols:
            numeric = pd.to_numeric(df[col], errors="coerce")
            stats[f"{col}_mean"] = [float(numeric.mean())]
            stats[f"{col}_std"] = [float(numeric.std())]
            stats[f"{col}_median"] = [float(numeric.median())]
        gold[f"{table}_stats"] = pd.DataFrame(stats)

        return gold

    def _aggregate_generic(self, table: str, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Generic aggregation for unknown table types"""
        gold = {}

        # Basic stats
        stats = {
            "table": [table],
            "total_rows": [len(df)],
            "total_columns": [len(df.columns)],
            "timestamp": [datetime.now().isoformat()],
        }

        # Add counts for each source
        if "_source" in df.columns:
            for src in df["_source"].unique():
                stats[f"source_{src}_count"] = [int((df["_source"] == src).sum())]

        gold[f"{table}_overview"] = pd.DataFrame(stats)

        return gold


# ======================== Query Engine ========================

class QueryEngine:
    """SQL query engine using DuckDB for Parquet files"""

    def execute(self, sql_query: str, layer: str = "gold", limit: int = 1000) -> Dict:
        """Execute SQL query against Lakehouse Parquet files"""
        layer_path = {"bronze": BRONZE_PATH, "silver": SILVER_PATH, "gold": GOLD_PATH}.get(layer)
        if not layer_path:
            raise ValueError(f"Unknown layer: {layer}")

        start = time.time()

        if DUCKDB_AVAILABLE:
            return self._execute_duckdb(sql_query, layer_path, limit, start)
        else:
            return self._execute_pandas(sql_query, layer_path, limit, start)

    def _execute_duckdb(self, sql_query: str, layer_path: Path, limit: int, start: float) -> Dict:
        """Execute via DuckDB (fast, supports full SQL)"""
        con = duckdb.connect()

        # Register all Parquet files as views
        for table_dir in layer_path.iterdir():
            if table_dir.is_dir() and not table_dir.name.startswith("_"):
                parquet_files = list(table_dir.rglob("*.parquet"))
                if parquet_files:
                    latest = sorted(parquet_files)[-1]
                    safe_name = table_dir.name.replace("-", "_").replace(".", "_")
                    con.execute(f"CREATE VIEW \"{safe_name}\" AS SELECT * FROM read_parquet('{latest}')")

        # Execute query with limit
        if "LIMIT" not in sql_query.upper():
            sql_query = f"{sql_query} LIMIT {limit}"

        result = con.execute(sql_query)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        results = []
        for row in rows:
            record = {}
            for i, col in enumerate(columns):
                val = row[i]
                if isinstance(val, (np.integer, np.int64)):
                    val = int(val)
                elif isinstance(val, (np.floating, np.float64)):
                    val = float(val)
                elif isinstance(val, np.bool_):
                    val = bool(val)
                record[col] = val
            results.append(record)

        con.close()

        return {
            "results": results,
            "row_count": len(results),
            "columns": columns,
            "execution_time_ms": round((time.time() - start) * 1000, 2),
            "engine": "duckdb",
        }

    def _execute_pandas(self, sql_query: str, layer_path: Path, limit: int, start: float) -> Dict:
        """Fallback: parse simple queries using pandas"""
        # Extract table name from query (simple parser)
        parts = sql_query.upper().split()
        table_name = None
        for i, p in enumerate(parts):
            if p == "FROM" and i + 1 < len(parts):
                table_name = parts[i + 1].strip('"').strip("'").lower()
                break

        if not table_name:
            raise ValueError("Could not parse table name from query")

        # Find the table
        table_dir = layer_path / table_name
        if not table_dir.exists():
            # Try with underscores
            table_name_clean = table_name.replace("-", "_").replace(".", "_")
            for d in layer_path.iterdir():
                if d.is_dir() and d.name.replace("-", "_").replace(".", "_") == table_name_clean:
                    table_dir = d
                    break

        if not table_dir.exists():
            raise FileNotFoundError(f"Table not found: {table_name}")

        parquet_files = list(table_dir.rglob("*.parquet"))
        if not parquet_files:
            return {"results": [], "row_count": 0, "columns": [], "execution_time_ms": 0, "engine": "pandas"}

        latest = sorted(parquet_files)[-1]
        df = pd.read_parquet(latest).head(limit)

        results = df.to_dict(orient="records")
        columns = list(df.columns)

        return {
            "results": results,
            "row_count": len(results),
            "columns": columns,
            "execution_time_ms": round((time.time() - start) * 1000, 2),
            "engine": "pandas_fallback",
        }


# ======================== FastAPI Application ========================

app = FastAPI(
    title="54Link Lakehouse Service",
    description="Unified data lakehouse API — Bronze/Silver/Gold medallion architecture",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

etl = MedallionETL()
query_engine = QueryEngine()
quality_engine = DataQualityEngine()
catalog = CatalogManager()


@app.get("/health")
async def health():
    """Service health check"""
    bronze_tables = len(list(BRONZE_PATH.iterdir())) if BRONZE_PATH.exists() else 0
    silver_tables = len(list(SILVER_PATH.iterdir())) if SILVER_PATH.exists() else 0
    gold_tables = len(list(GOLD_PATH.iterdir())) if GOLD_PATH.exists() else 0

    return {
        "status": "healthy",
        "service": "54link-lakehouse",
        "version": "1.0.0",
        "engine": "duckdb" if DUCKDB_AVAILABLE else "pandas_fallback",
        "layers": {
            "bronze": {"tables": bronze_tables},
            "silver": {"tables": silver_tables},
            "gold": {"tables": gold_tables},
        },
        "root_path": str(LAKEHOUSE_ROOT),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/v1/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """Ingest records into Bronze layer"""
    records = req.data if isinstance(req.data, list) else [req.data]

    # Data quality validation
    issues = []
    for record in records:
        record_issues = quality_engine.validate_record(req.table, record)
        issues.extend(record_issues)

    if issues:
        logger.warning(f"[Ingest] Quality issues in {req.table}: {issues[:5]}")

    result = etl.ingest_to_bronze(req.table, records, source=req.source)

    return IngestResponse(
        status="ok",
        table=req.table,
        records_ingested=result["records"],
        layer="bronze",
        version=result["version"],
        partition=result["partition"],
    )


@app.post("/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Execute SQL query against Lakehouse"""
    try:
        result = query_engine.execute(req.sql, layer=req.layer, limit=req.limit)
        return QueryResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")


@app.get("/v1/catalog")
async def list_catalog(layer: Optional[str] = None):
    """List all tables in the catalog"""
    tables = catalog.list_tables(layer=layer)
    return {
        "tables": tables,
        "total": len(tables),
        "layers": {
            "bronze": len([t for t in tables if t.get("layer") == "bronze"]),
            "silver": len([t for t in tables if t.get("layer") == "silver"]),
            "gold": len([t for t in tables if t.get("layer") == "gold"]),
        },
    }


@app.get("/v1/catalog/{table_name}")
async def get_table_catalog(table_name: str, layer: Optional[str] = None):
    """Get catalog entry for a specific table"""
    entry = catalog.get_table(table_name, layer=layer)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")
    return entry


@app.post("/v1/etl/promote")
async def etl_promote(req: ETLPromoteRequest):
    """Run ETL promotion: Bronze→Silver or Silver→Gold"""
    try:
        if req.source_layer == "bronze" and req.target_layer == "silver":
            return etl.promote_to_silver(req.table)
        elif req.source_layer == "silver" and req.target_layer == "gold":
            return etl.promote_to_gold(req.table)
        elif req.source_layer == "bronze" and req.target_layer == "gold":
            # Full pipeline
            silver_result = etl.promote_to_silver(req.table)
            gold_result = etl.promote_to_gold(req.table)
            return {"silver": silver_result, "gold": gold_result}
        else:
            raise HTTPException(status_code=400, detail=f"Invalid promotion: {req.source_layer} → {req.target_layer}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/v1/quality/{table_name}")
async def get_quality_report(table_name: str, layer: str = "bronze"):
    """Generate data quality report for a table"""
    layer_path = {"bronze": BRONZE_PATH, "silver": SILVER_PATH, "gold": GOLD_PATH}.get(layer)
    if not layer_path:
        raise HTTPException(status_code=400, detail=f"Unknown layer: {layer}")

    table_dir = layer_path / table_name
    if not table_dir.exists():
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    parquet_files = list(table_dir.rglob("*.parquet"))
    if not parquet_files:
        raise HTTPException(status_code=404, detail=f"No data in {layer}/{table_name}")

    latest = sorted(parquet_files)[-1]
    df = pd.read_parquet(latest)

    report = quality_engine.generate_quality_report(table_name, layer, df)

    # Persist report
    report_path = QUALITY_PATH / f"{layer}__{table_name}.json"
    with open(report_path, "w") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)

    return report


@app.get("/v1/layers/stats")
async def layer_stats():
    """Get statistics for each Medallion layer"""
    stats = {}
    for layer_name, layer_path in [("bronze", BRONZE_PATH), ("silver", SILVER_PATH), ("gold", GOLD_PATH)]:
        tables = []
        total_size = 0
        total_rows = 0

        if layer_path.exists():
            for table_dir in layer_path.iterdir():
                if table_dir.is_dir() and not table_dir.name.startswith("_"):
                    parquet_files = list(table_dir.rglob("*.parquet"))
                    table_size = sum(f.stat().st_size for f in parquet_files)
                    total_size += table_size
                    tables.append({
                        "name": table_dir.name,
                        "files": len(parquet_files),
                        "size_bytes": table_size,
                    })

        stats[layer_name] = {
            "tables": tables,
            "table_count": len(tables),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    return stats


# ======================== CLI Entry Point ========================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("LAKEHOUSE_PORT", "8156"))
    logger.info(f"Starting Lakehouse Service on port {port}")
    logger.info(f"Root: {LAKEHOUSE_ROOT}")
    logger.info(f"Engine: {'DuckDB' if DUCKDB_AVAILABLE else 'Pandas fallback'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
