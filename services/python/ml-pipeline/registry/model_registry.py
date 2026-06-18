"""
Model Registry

Provides:
- Model versioning and metadata tracking
- Model lifecycle management (staging → production → archived)
- Model comparison and promotion
- Artifact storage (weights, configs, metrics)
- Deployment tracking (which model is serving where)

Storage:
- Model artifacts: file system (or S3 in production)
- Metadata: JSON (or PostgreSQL in production)
"""

import os
import json
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class ModelStage(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelType(str, Enum):
    FRAUD_DETECTION = "fraud_detection"
    CREDIT_SCORING = "credit_scoring"
    GNN_FRAUD = "gnn_fraud"
    ANOMALY_DETECTION = "anomaly_detection"
    DEFAULT_PREDICTION = "default_prediction"


class ModelRegistry:
    """Central registry for ML model versioning and lifecycle management"""

    def __init__(self, registry_path: str = None):
        self.registry_path = Path(registry_path or os.getenv(
            "MODEL_REGISTRY_PATH", 
            str(Path(__file__).parent.parent / "models" / "registry")
        ))
        self.registry_path.mkdir(parents=True, exist_ok=True)
        self.artifacts_path = self.registry_path / "artifacts"
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.registry_path / "metadata"
        self.metadata_path.mkdir(parents=True, exist_ok=True)

    def register_model(self, model_name: str, model_type: ModelType,
                      artifact_path: str, metrics: Dict[str, float],
                      parameters: Dict[str, Any] = None,
                      description: str = "",
                      tags: Dict[str, str] = None) -> Dict[str, Any]:
        """Register a new model version

        Args:
            model_name: Model identifier (e.g., 'fraud_xgboost')
            model_type: Type category
            artifact_path: Path to model artifact file
            metrics: Training/evaluation metrics
            parameters: Hyperparameters used
            description: Human-readable description
            tags: Additional metadata tags

        Returns:
            Registration metadata with version info
        """
        # Determine version
        existing_versions = self._get_versions(model_name)
        version = max([v["version"] for v in existing_versions], default=0) + 1

        # Compute artifact hash
        artifact_file = Path(artifact_path)
        if artifact_file.exists():
            file_hash = hashlib.sha256(artifact_file.read_bytes()).hexdigest()[:16]
            file_size = artifact_file.stat().st_size
        else:
            file_hash = "not_found"
            file_size = 0

        # Copy artifact to registry
        dest_dir = self.artifacts_path / model_name / f"v{version}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        if artifact_file.exists():
            shutil.copy2(artifact_path, dest_dir / artifact_file.name)

        # Create metadata
        metadata = {
            "model_name": model_name,
            "model_type": model_type.value if isinstance(model_type, ModelType) else model_type,
            "version": version,
            "stage": ModelStage.DEVELOPMENT.value,
            "registered_at": datetime.now().isoformat(),
            "description": description,
            "artifact_path": str(dest_dir / artifact_file.name),
            "artifact_hash": file_hash,
            "artifact_size_bytes": file_size,
            "metrics": metrics,
            "parameters": parameters or {},
            "tags": tags or {},
            "promoted_at": None,
            "deployed_at": None,
            "deployment_endpoint": None,
        }

        # Save metadata
        meta_file = self.metadata_path / f"{model_name}_v{version}.json"
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Registered {model_name} v{version} (stage: development)")
        return metadata

    def promote_model(self, model_name: str, version: int,
                     stage: ModelStage, reason: str = "") -> Dict[str, Any]:
        """Promote a model to a new stage

        Args:
            model_name: Model identifier
            version: Version to promote
            stage: Target stage
            reason: Reason for promotion

        Returns:
            Updated metadata
        """
        metadata = self._get_version_metadata(model_name, version)
        if not metadata:
            raise ValueError(f"Model {model_name} v{version} not found")

        old_stage = metadata["stage"]
        metadata["stage"] = stage.value
        metadata["promoted_at"] = datetime.now().isoformat()
        metadata["promotion_reason"] = reason

        # If promoting to production, demote current production model
        if stage == ModelStage.PRODUCTION:
            current_prod = self.get_production_model(model_name)
            if current_prod and current_prod["version"] != version:
                self.promote_model(
                    model_name, current_prod["version"],
                    ModelStage.ARCHIVED,
                    reason=f"Replaced by v{version}"
                )

        # Save updated metadata
        meta_file = self.metadata_path / f"{model_name}_v{version}.json"
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Promoted {model_name} v{version}: {old_stage} → {stage.value}")
        return metadata

    def get_production_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get the current production model for a given name"""
        versions = self._get_versions(model_name)
        prod_versions = [v for v in versions if v.get("stage") == ModelStage.PRODUCTION.value]
        if prod_versions:
            return max(prod_versions, key=lambda v: v["version"])
        return None

    def get_model_artifact_path(self, model_name: str, version: int = None) -> Optional[str]:
        """Get path to model artifact (latest production if version not specified)"""
        if version:
            meta = self._get_version_metadata(model_name, version)
        else:
            meta = self.get_production_model(model_name)
            if not meta:
                # Fall back to latest version
                versions = self._get_versions(model_name)
                if versions:
                    meta = max(versions, key=lambda v: v["version"])

        if meta:
            return meta.get("artifact_path")
        return None

    def compare_models(self, model_name: str, version_a: int, version_b: int) -> Dict[str, Any]:
        """Compare metrics between two model versions"""
        meta_a = self._get_version_metadata(model_name, version_a)
        meta_b = self._get_version_metadata(model_name, version_b)

        if not meta_a or not meta_b:
            raise ValueError(f"One or both versions not found")

        comparison = {
            "model_name": model_name,
            "version_a": version_a,
            "version_b": version_b,
            "metrics_a": meta_a["metrics"],
            "metrics_b": meta_b["metrics"],
            "improvements": {},
        }

        # Calculate metric improvements
        for metric in meta_a["metrics"]:
            if metric in meta_b["metrics"]:
                val_a = meta_a["metrics"][metric]
                val_b = meta_b["metrics"][metric]
                if val_a != 0:
                    pct_change = (val_b - val_a) / abs(val_a) * 100
                else:
                    pct_change = 0
                comparison["improvements"][metric] = {
                    "version_a": val_a,
                    "version_b": val_b,
                    "change_pct": round(pct_change, 2),
                    "improved": val_b > val_a,
                }

        return comparison

    def list_models(self, model_type: ModelType = None, stage: ModelStage = None) -> List[Dict]:
        """List all registered models with optional filtering"""
        all_models = []
        for meta_file in sorted(self.metadata_path.glob("*.json")):
            with open(meta_file) as f:
                meta = json.load(f)
            if model_type and meta.get("model_type") != model_type.value:
                continue
            if stage and meta.get("stage") != stage.value:
                continue
            all_models.append(meta)
        return all_models

    def _get_versions(self, model_name: str) -> List[Dict]:
        """Get all versions for a model"""
        versions = []
        for meta_file in sorted(self.metadata_path.glob(f"{model_name}_v*.json")):
            with open(meta_file) as f:
                versions.append(json.load(f))
        return versions

    def _get_version_metadata(self, model_name: str, version: int) -> Optional[Dict]:
        """Get metadata for a specific version"""
        meta_file = self.metadata_path / f"{model_name}_v{version}.json"
        if meta_file.exists():
            with open(meta_file) as f:
                return json.load(f)
        return None
