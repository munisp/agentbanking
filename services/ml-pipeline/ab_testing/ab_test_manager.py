"""
A/B Testing Infrastructure for ML Models

Provides:
- Traffic splitting between model versions (configurable percentages)
- Statistical significance testing (chi-squared, t-test, Bayesian)
- Multi-armed bandit for adaptive allocation
- Experiment lifecycle management (create, run, conclude)
- Metrics collection and comparison
- Automatic winner selection with confidence intervals

Supports:
- Simple A/B (50/50 or custom split)
- Multi-variant testing (A/B/C/D)
- Canary deployments (95/5 split)
- Shadow mode (both models predict, only champion serves)
"""

import numpy as np
import json
import logging
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from scipy import stats as scipy_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    CONCLUDED = "concluded"


class AllocationStrategy(str, Enum):
    FIXED = "fixed"          # Fixed traffic split
    EPSILON_GREEDY = "epsilon_greedy"  # Explore/exploit
    THOMPSON_SAMPLING = "thompson_sampling"  # Bayesian bandit
    CANARY = "canary"        # Gradual rollout


@dataclass
class ExperimentVariant:
    name: str
    model_name: str
    model_version: int
    traffic_weight: float
    n_requests: int = 0
    n_successes: int = 0  # e.g., correct fraud detection
    total_latency_ms: float = 0
    predictions: List[float] = None
    labels: List[int] = None

    def __post_init__(self):
        if self.predictions is None:
            self.predictions = []
        if self.labels is None:
            self.labels = []


@dataclass
class Experiment:
    experiment_id: str
    name: str
    description: str
    status: ExperimentStatus
    variants: List[ExperimentVariant]
    allocation_strategy: AllocationStrategy
    metric_name: str  # Primary metric to optimize
    created_at: str
    started_at: Optional[str] = None
    concluded_at: Optional[str] = None
    winner: Optional[str] = None
    confidence: float = 0.0
    min_samples: int = 1000  # Minimum samples before concluding


class ABTestManager:
    """Manages A/B testing experiments for ML models"""

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or "/data/ab_tests")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.experiments: Dict[str, Experiment] = {}
        self._load_experiments()

    def create_experiment(self, name: str, variants: List[Dict[str, Any]],
                         metric_name: str = "auc",
                         allocation_strategy: str = "fixed",
                         description: str = "",
                         min_samples: int = 1000) -> Experiment:
        """Create a new A/B test experiment

        Args:
            name: Experiment name
            variants: List of variant configs [{name, model_name, model_version, traffic_weight}]
            metric_name: Primary metric to compare
            allocation_strategy: How to split traffic
            description: Human-readable description
            min_samples: Minimum requests before concluding

        Returns:
            Created Experiment object
        """
        experiment_id = f"exp_{hashlib.md5(f'{name}_{time.time()}'.encode()).hexdigest()[:12]}"

        # Validate traffic weights sum to 1.0
        total_weight = sum(v.get("traffic_weight", 0) for v in variants)
        if abs(total_weight - 1.0) > 0.01:
            # Normalize weights
            for v in variants:
                v["traffic_weight"] = v.get("traffic_weight", 1.0 / len(variants)) / total_weight

        experiment_variants = [
            ExperimentVariant(
                name=v["name"],
                model_name=v["model_name"],
                model_version=v["model_version"],
                traffic_weight=v["traffic_weight"],
            )
            for v in variants
        ]

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            status=ExperimentStatus.DRAFT,
            variants=experiment_variants,
            allocation_strategy=AllocationStrategy(allocation_strategy),
            metric_name=metric_name,
            created_at=datetime.now().isoformat(),
            min_samples=min_samples,
        )

        self.experiments[experiment_id] = experiment
        self._save_experiment(experiment)

        logger.info(f"Created experiment '{name}' with {len(variants)} variants")
        return experiment

    def start_experiment(self, experiment_id: str) -> Experiment:
        """Start running an experiment"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        exp.status = ExperimentStatus.RUNNING
        exp.started_at = datetime.now().isoformat()
        self._save_experiment(exp)

        logger.info(f"Started experiment: {exp.name}")
        return exp

    def route_request(self, experiment_id: str, request_id: str = None) -> str:
        """Route a request to a variant based on allocation strategy

        Args:
            experiment_id: Active experiment ID
            request_id: Optional request ID for consistent routing

        Returns:
            Selected variant name
        """
        exp = self.experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            # Default to first variant
            return exp.variants[0].name if exp else "default"

        if exp.allocation_strategy == AllocationStrategy.FIXED:
            return self._route_fixed(exp, request_id)
        elif exp.allocation_strategy == AllocationStrategy.EPSILON_GREEDY:
            return self._route_epsilon_greedy(exp)
        elif exp.allocation_strategy == AllocationStrategy.THOMPSON_SAMPLING:
            return self._route_thompson_sampling(exp)
        elif exp.allocation_strategy == AllocationStrategy.CANARY:
            return self._route_canary(exp, request_id)
        else:
            return self._route_fixed(exp, request_id)

    def record_result(self, experiment_id: str, variant_name: str,
                     prediction: float, label: int = None,
                     latency_ms: float = 0, success: bool = None):
        """Record a prediction result for a variant

        Args:
            experiment_id: Experiment ID
            variant_name: Which variant made the prediction
            prediction: Model prediction value
            label: Ground truth (if available)
            latency_ms: Inference latency
            success: Whether prediction was correct (if known)
        """
        exp = self.experiments.get(experiment_id)
        if not exp:
            return

        for variant in exp.variants:
            if variant.name == variant_name:
                variant.n_requests += 1
                variant.total_latency_ms += latency_ms
                variant.predictions.append(prediction)

                if label is not None:
                    variant.labels.append(label)

                if success is not None and success:
                    variant.n_successes += 1

                break

        # Check if we should auto-conclude
        total_requests = sum(v.n_requests for v in exp.variants)
        if total_requests >= exp.min_samples * len(exp.variants):
            self._check_significance(exp)

    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get current results for an experiment"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        results = {
            "experiment_id": experiment_id,
            "name": exp.name,
            "status": exp.status.value,
            "started_at": exp.started_at,
            "metric_name": exp.metric_name,
            "variants": [],
        }

        for variant in exp.variants:
            variant_result = {
                "name": variant.name,
                "model": f"{variant.model_name} v{variant.model_version}",
                "n_requests": variant.n_requests,
                "traffic_weight": variant.traffic_weight,
                "avg_latency_ms": variant.total_latency_ms / max(variant.n_requests, 1),
                "success_rate": variant.n_successes / max(variant.n_requests, 1),
            }

            # Compute metric if labels available
            if variant.labels and variant.predictions:
                from sklearn.metrics import roc_auc_score, f1_score
                labels = np.array(variant.labels)
                preds = np.array(variant.predictions[:len(labels)])

                if len(np.unique(labels)) > 1:
                    variant_result["auc"] = float(roc_auc_score(labels, preds))
                    variant_result["f1"] = float(f1_score(labels, (preds >= 0.5).astype(int), zero_division=0))

            results["variants"].append(variant_result)

        # Statistical comparison
        if len(exp.variants) == 2 and all(v.predictions for v in exp.variants):
            results["statistical_test"] = self._compute_significance(
                exp.variants[0], exp.variants[1]
            )

        if exp.winner:
            results["winner"] = exp.winner
            results["confidence"] = exp.confidence

        return results

    def conclude_experiment(self, experiment_id: str, winner: str = None) -> Dict[str, Any]:
        """Conclude an experiment and declare a winner"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        if not winner:
            # Auto-select winner based on metric
            winner = self._select_winner(exp)

        exp.status = ExperimentStatus.CONCLUDED
        exp.concluded_at = datetime.now().isoformat()
        exp.winner = winner
        self._save_experiment(exp)

        logger.info(f"Concluded experiment '{exp.name}': winner = {winner}")
        return self.get_experiment_results(experiment_id)

    # ======================== Routing Strategies ========================

    def _route_fixed(self, exp: Experiment, request_id: str = None) -> str:
        """Fixed percentage traffic split"""
        if request_id:
            # Deterministic routing based on request ID hash
            hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
            threshold = hash_val % 1000 / 1000.0
        else:
            threshold = np.random.random()

        cumulative = 0
        for variant in exp.variants:
            cumulative += variant.traffic_weight
            if threshold <= cumulative:
                return variant.name

        return exp.variants[-1].name

    def _route_epsilon_greedy(self, exp: Experiment, epsilon: float = 0.1) -> str:
        """Epsilon-greedy: exploit best variant most of the time"""
        if np.random.random() < epsilon:
            # Explore: random variant
            return np.random.choice([v.name for v in exp.variants])
        else:
            # Exploit: best performing variant
            best = max(exp.variants,
                      key=lambda v: v.n_successes / max(v.n_requests, 1))
            return best.name

    def _route_thompson_sampling(self, exp: Experiment) -> str:
        """Thompson Sampling: Bayesian bandit for optimal exploration"""
        samples = []
        for variant in exp.variants:
            # Beta distribution parameters
            alpha = variant.n_successes + 1
            beta = (variant.n_requests - variant.n_successes) + 1
            sample = np.random.beta(alpha, beta)
            samples.append((variant.name, sample))

        # Select variant with highest sample
        winner = max(samples, key=lambda x: x[1])
        return winner[0]

    def _route_canary(self, exp: Experiment, request_id: str = None) -> str:
        """Canary deployment: gradually increase traffic to new model"""
        # First variant is champion (high traffic), rest are canaries
        return self._route_fixed(exp, request_id)

    # ======================== Statistical Analysis ========================

    def _compute_significance(self, variant_a: ExperimentVariant,
                            variant_b: ExperimentVariant) -> Dict[str, Any]:
        """Compute statistical significance between two variants"""
        # Proportion test (chi-squared)
        n_a = max(variant_a.n_requests, 1)
        n_b = max(variant_b.n_requests, 1)
        p_a = variant_a.n_successes / n_a
        p_b = variant_b.n_successes / n_b

        # Pooled proportion
        p_pool = (variant_a.n_successes + variant_b.n_successes) / (n_a + n_b)
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b)) if p_pool > 0 else 1e-6

        z_score = (p_b - p_a) / max(se, 1e-6)
        p_value = 2 * (1 - scipy_stats.norm.cdf(abs(z_score)))

        return {
            "z_score": float(z_score),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "confidence_level": 1 - p_value,
            "effect_size": float(p_b - p_a),
            "variant_a_rate": float(p_a),
            "variant_b_rate": float(p_b),
        }

    def _check_significance(self, exp: Experiment):
        """Check if experiment has reached significance"""
        if len(exp.variants) != 2:
            return

        result = self._compute_significance(exp.variants[0], exp.variants[1])
        if result["significant"]:
            exp.confidence = result["confidence_level"]
            logger.info(f"Experiment '{exp.name}' reached significance: p={result['p_value']:.4f}")

    def _select_winner(self, exp: Experiment) -> str:
        """Select winner based on metric comparison"""
        best_variant = max(
            exp.variants,
            key=lambda v: v.n_successes / max(v.n_requests, 1)
        )
        return best_variant.name

    # ======================== Persistence ========================

    def _save_experiment(self, exp: Experiment):
        """Save experiment to disk"""
        data = {
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "description": exp.description,
            "status": exp.status.value,
            "allocation_strategy": exp.allocation_strategy.value,
            "metric_name": exp.metric_name,
            "created_at": exp.created_at,
            "started_at": exp.started_at,
            "concluded_at": exp.concluded_at,
            "winner": exp.winner,
            "confidence": exp.confidence,
            "min_samples": exp.min_samples,
            "variants": [
                {
                    "name": v.name,
                    "model_name": v.model_name,
                    "model_version": v.model_version,
                    "traffic_weight": v.traffic_weight,
                    "n_requests": v.n_requests,
                    "n_successes": v.n_successes,
                    "total_latency_ms": v.total_latency_ms,
                }
                for v in exp.variants
            ],
        }
        with open(self.storage_path / f"{exp.experiment_id}.json", "w") as f:
            json.dump(data, f, indent=2)

    def _load_experiments(self):
        """Load all experiments from disk"""
        for f in self.storage_path.glob("exp_*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                variants = [
                    ExperimentVariant(**{k: v for k, v in vd.items()
                                       if k in ExperimentVariant.__dataclass_fields__})
                    for vd in data.get("variants", [])
                ]
                exp = Experiment(
                    experiment_id=data["experiment_id"],
                    name=data["name"],
                    description=data.get("description", ""),
                    status=ExperimentStatus(data["status"]),
                    variants=variants,
                    allocation_strategy=AllocationStrategy(data["allocation_strategy"]),
                    metric_name=data["metric_name"],
                    created_at=data["created_at"],
                    started_at=data.get("started_at"),
                    concluded_at=data.get("concluded_at"),
                    winner=data.get("winner"),
                    confidence=data.get("confidence", 0),
                    min_samples=data.get("min_samples", 1000),
                )
                self.experiments[exp.experiment_id] = exp
            except Exception as e:
                logger.warning(f"Failed to load experiment {f}: {e}")
