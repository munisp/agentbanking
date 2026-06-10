"""
Delta Lake Integration for ML Pipeline

Provides:
- Versioned training data storage (time-travel for reproducibility)
- Feature store with point-in-time lookups
- Data lineage tracking
- Incremental data ingestion from production DB
- Schema evolution support

Uses Delta Lake (via deltalake Python package) for ACID transactions
on Parquet files, enabling ML-specific data management:
- Rollback training data to any version
- Audit trail of data changes
- Concurrent read/write safety
"""

import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

try:
    from deltalake import DeltaTable, write_deltalake
    DELTA_AVAILABLE = True
except ImportError:
    DELTA_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

LAKEHOUSE_ROOT = Path(os.getenv("LAKEHOUSE_ROOT", "/data/lakehouse"))


class DeltaLakeStore:
    """Delta Lake-based feature store and training data manager"""

    def __init__(self, root_path: str = None):
        self.root = Path(root_path or LAKEHOUSE_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.root / "_metadata"
        self.metadata_path.mkdir(parents=True, exist_ok=True)

        if not DELTA_AVAILABLE:
            logger.warning("deltalake package not installed. Using Parquet fallback mode.")

    # ======================== Table Management ========================

    def write_training_data(self, df: pd.DataFrame, table_name: str, 
                           version_tag: str = None, mode: str = "overwrite") -> Dict[str, Any]:
        """Write training data to versioned Delta table

        Args:
            df: Training data DataFrame
            table_name: Logical table name (e.g., 'fraud_transactions', 'credit_features')
            version_tag: Optional tag for this version (e.g., 'v1.0', '2024-01-training')
            mode: 'overwrite' or 'append'

        Returns:
            Metadata dict with version info
        """
        table_path = self.root / table_name
        table_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat()
        n_rows = len(df)
        n_cols = len(df.columns)

        if DELTA_AVAILABLE:
            write_deltalake(
                str(table_path),
                df,
                mode=mode,
                schema_mode="merge",
            )
            # Get version info
            dt = DeltaTable(str(table_path))
            version = dt.version()
        else:
            # Fallback: write as timestamped Parquet
            version = int(time.time())
            parquet_path = table_path / f"v{version}.parquet"
            df.to_parquet(parquet_path, index=False)

        # Save metadata
        meta = {
            "table_name": table_name,
            "version": version,
            "version_tag": version_tag,
            "timestamp": timestamp,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "mode": mode,
        }

        meta_file = self.metadata_path / f"{table_name}_v{version}.json"
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Written {n_rows} rows to {table_name} (version {version})")
        return meta

    def read_training_data(self, table_name: str, version: Optional[int] = None) -> pd.DataFrame:
        """Read training data from Delta table (optionally at specific version)

        Args:
            table_name: Logical table name
            version: Optional version number (None = latest)

        Returns:
            DataFrame with training data
        """
        table_path = self.root / table_name

        if DELTA_AVAILABLE:
            if version is not None:
                dt = DeltaTable(str(table_path), version=version)
            else:
                dt = DeltaTable(str(table_path))
            df = dt.to_pandas()
        else:
            # Fallback: read latest Parquet file
            parquet_files = sorted(table_path.glob("*.parquet"))
            if not parquet_files:
                raise FileNotFoundError(f"No data found for table: {table_name}")
            if version:
                target = table_path / f"v{version}.parquet"
                if target.exists():
                    df = pd.read_parquet(target)
                else:
                    df = pd.read_parquet(parquet_files[-1])
            else:
                df = pd.read_parquet(parquet_files[-1])

        logger.info(f"Read {len(df)} rows from {table_name}")
        return df

    def list_versions(self, table_name: str) -> List[Dict]:
        """List all versions of a table with metadata"""
        meta_files = sorted(self.metadata_path.glob(f"{table_name}_v*.json"))
        versions = []
        for mf in meta_files:
            with open(mf) as f:
                versions.append(json.load(f))
        return versions

    # ======================== Feature Store ========================

    def write_features(self, df: pd.DataFrame, feature_group: str,
                      entity_key: str = "customer_id") -> Dict[str, Any]:
        """Write computed features to feature store

        Args:
            df: Feature DataFrame (must include entity_key and event_timestamp)
            feature_group: Logical feature group name
            entity_key: Column used as entity identifier

        Returns:
            Metadata dict
        """
        # Add ingestion timestamp if not present
        if "feature_timestamp" not in df.columns:
            df = df.copy()
            df["feature_timestamp"] = datetime.now().isoformat()

        return self.write_training_data(df, f"features/{feature_group}", mode="append")

    def get_features_point_in_time(self, entity_ids: List[str], feature_group: str,
                                    timestamp: str, entity_key: str = "customer_id") -> pd.DataFrame:
        """Point-in-time feature lookup (prevents data leakage in training)

        Args:
            entity_ids: List of entity IDs to look up
            feature_group: Feature group name
            timestamp: Point-in-time cutoff (ISO format)
            entity_key: Entity key column

        Returns:
            Features as of the specified timestamp
        """
        df = self.read_training_data(f"features/{feature_group}")

        # Filter to requested entities
        df = df[df[entity_key].isin(entity_ids)]

        # Point-in-time: only use features available before timestamp
        if "feature_timestamp" in df.columns:
            df = df[df["feature_timestamp"] <= timestamp]

        # Take latest feature per entity
        df = df.sort_values("feature_timestamp").groupby(entity_key).last().reset_index()

        return df

    # ======================== Data Lineage ========================

    def log_training_run(self, run_id: str, input_tables: List[str],
                        output_model: str, metrics: Dict[str, float],
                        parameters: Dict[str, Any]) -> Dict:
        """Log a training run for data lineage tracking"""
        lineage = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "input_tables": input_tables,
            "output_model": output_model,
            "metrics": metrics,
            "parameters": parameters,
        }

        lineage_dir = self.metadata_path / "lineage"
        lineage_dir.mkdir(parents=True, exist_ok=True)
        with open(lineage_dir / f"{run_id}.json", "w") as f:
            json.dump(lineage, f, indent=2)

        logger.info(f"Logged training run: {run_id}")
        return lineage

    # ======================== Production Data Ingestion ========================

    def ingest_from_postgres(self, connection_url: str, query: str,
                            table_name: str, incremental_column: str = None,
                            last_value: Any = None) -> Dict[str, Any]:
        """Ingest data from PostgreSQL into Delta Lake

        Args:
            connection_url: PostgreSQL connection string
            query: SQL query to execute
            table_name: Target Delta table name
            incremental_column: Column for incremental ingestion
            last_value: Last ingested value for incremental mode

        Returns:
            Ingestion metadata
        """
        try:
            from sqlalchemy import create_engine
            engine = create_engine(connection_url)

            if incremental_column and last_value:
                query = f"{query} WHERE {incremental_column} > '{last_value}'"

            df = pd.read_sql(query, engine)
            mode = "append" if incremental_column else "overwrite"

            meta = self.write_training_data(df, table_name, mode=mode)
            meta["source"] = "postgresql"
            meta["query"] = query
            meta["incremental"] = incremental_column is not None

            logger.info(f"Ingested {len(df)} rows from PostgreSQL → {table_name}")
            return meta

        except Exception as e:
            logger.error(f"PostgreSQL ingestion failed: {e}")
            raise

    def compact_table(self, table_name: str) -> Dict[str, Any]:
        """Compact small files in a Delta table (optimization)"""
        table_path = self.root / table_name

        if DELTA_AVAILABLE:
            dt = DeltaTable(str(table_path))
            result = dt.optimize.compact()
            logger.info(f"Compacted {table_name}: {result}")
            return {"compacted": True, "table": table_name}
        else:
            # Fallback: merge all Parquet files into one
            parquet_files = sorted(table_path.glob("*.parquet"))
            if len(parquet_files) > 1:
                dfs = [pd.read_parquet(f) for f in parquet_files]
                merged = pd.concat(dfs, ignore_index=True)
                # Remove old files
                for f in parquet_files:
                    f.unlink()
                # Write merged
                merged.to_parquet(table_path / f"v{int(time.time())}.parquet", index=False)
                logger.info(f"Compacted {len(parquet_files)} files into 1")
            return {"compacted": True, "table": table_name}
