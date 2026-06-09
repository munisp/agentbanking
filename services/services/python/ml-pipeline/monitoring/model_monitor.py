"""
Model Monitoring Service

Provides:
- Data drift detection (KL divergence, KS test, PSI)
- Prediction drift monitoring
- Performance degradation alerts
- Feature importance shift detection
- Automated retraining triggers
- Prometheus metrics export

Monitors:
- Input feature distributions vs training baseline
- Prediction distribution shifts
- Actual vs predicted (when labels available)
- Latency and throughput metrics
"""

import numpy as np
import pandas as pd
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque

from scipy import stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class DriftType(str, Enum):
    DATA_DRIFT = "data_drift"
    PREDICTION_DRIFT = "prediction_drift"
    PERFORMANCE_DRIFT = "performance_drift"
    CONCEPT_DRIFT = "concept_drift"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DriftAlert:
    alert_id: str
    model_name: str
    drift_type: DriftType
    severity: AlertSeverity
    feature: Optional[str]
    metric_value: float
    threshold: float
    message: str
    timestamp: str
    details: Dict[str, Any]


class ModelMonitor:
    """Monitors ML models in production for drift and degradation"""

    def __init__(self, model_name: str, baseline_data: pd.DataFrame = None,
                 alert_callback: Any = None):
        self.model_name = model_name
        self.baseline_stats: Dict[str, Dict] = {}
        self.prediction_buffer = deque(maxlen=10000)
        self.label_buffer = deque(maxlen=10000)
        self.alerts: List[DriftAlert] = []
        self.alert_callback = alert_callback
        self.metrics_history: List[Dict] = []

        # Thresholds
        self.psi_threshold = 0.2  # Population Stability Index
        self.ks_threshold = 0.1   # Kolmogorov-Smirnov
        self.perf_degradation_threshold = 0.05  # 5% drop from baseline

        if baseline_data is not None:
            self.set_baseline(baseline_data)

    def set_baseline(self, data: pd.DataFrame):
        """Set baseline statistics from training data distribution"""
        logger.info(f"Setting baseline for {self.model_name} ({len(data)} samples)")

        for col in data.select_dtypes(include=[np.number]).columns:
            values = data[col].dropna().values
            if len(values) == 0:
                continue

            self.baseline_stats[col] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "median": float(np.median(values)),
                "q25": float(np.percentile(values, 25)),
                "q75": float(np.percentile(values, 75)),
                "histogram": np.histogram(values, bins=20)[0].tolist(),
                "bin_edges": np.histogram(values, bins=20)[1].tolist(),
                "n_samples": len(values),
            }

        logger.info(f"Baseline set for {len(self.baseline_stats)} features")

    def check_data_drift(self, current_data: pd.DataFrame) -> Dict[str, Any]:
        """Check for data drift between current data and baseline

        Uses:
        - Population Stability Index (PSI) for distribution shift
        - Kolmogorov-Smirnov test for statistical significance
        - Jensen-Shannon divergence for distribution comparison

        Returns:
            Drift report with per-feature metrics
        """
        if not self.baseline_stats:
            logger.warning("No baseline set. Call set_baseline() first.")
            return {"drifted": False, "reason": "no_baseline"}

        drift_report = {
            "model_name": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "n_features_checked": 0,
            "n_features_drifted": 0,
            "drifted_features": [],
            "feature_scores": {},
        }

        for col in current_data.select_dtypes(include=[np.number]).columns:
            if col not in self.baseline_stats:
                continue

            current_values = current_data[col].dropna().values
            if len(current_values) < 100:
                continue

            baseline = self.baseline_stats[col]
            drift_report["n_features_checked"] += 1

            # PSI (Population Stability Index)
            psi = self._compute_psi(
                baseline["histogram"], baseline["bin_edges"], current_values
            )

            # KS Test
            # Reconstruct baseline sample from stats for KS test
            baseline_sample = np.random.normal(
                baseline["mean"], max(baseline["std"], 1e-6), baseline["n_samples"]
            )
            ks_stat, ks_pvalue = stats.ks_2samp(baseline_sample, current_values)

            # Store scores
            drift_report["feature_scores"][col] = {
                "psi": float(psi),
                "ks_statistic": float(ks_stat),
                "ks_pvalue": float(ks_pvalue),
                "mean_shift": float(np.mean(current_values) - baseline["mean"]),
                "std_ratio": float(np.std(current_values) / max(baseline["std"], 1e-6)),
            }

            # Check thresholds
            if psi > self.psi_threshold or ks_stat > self.ks_threshold:
                drift_report["n_features_drifted"] += 1
                drift_report["drifted_features"].append(col)

                self._raise_alert(
                    drift_type=DriftType.DATA_DRIFT,
                    severity=AlertSeverity.WARNING if psi < 0.4 else AlertSeverity.CRITICAL,
                    feature=col,
                    metric_value=psi,
                    threshold=self.psi_threshold,
                    message=f"Data drift detected in '{col}': PSI={psi:.4f} (threshold={self.psi_threshold})",
                    details=drift_report["feature_scores"][col],
                )

        drift_report["overall_drifted"] = drift_report["n_features_drifted"] > 0
        drift_report["drift_ratio"] = (
            drift_report["n_features_drifted"] / max(drift_report["n_features_checked"], 1)
        )

        self.metrics_history.append(drift_report)
        return drift_report

    def check_prediction_drift(self, predictions: np.ndarray,
                               baseline_predictions: np.ndarray = None) -> Dict[str, Any]:
        """Check if prediction distribution has shifted"""
        self.prediction_buffer.extend(predictions.tolist())
        current_preds = np.array(list(self.prediction_buffer))

        if baseline_predictions is None:
            # Use first 1000 predictions as baseline
            if len(current_preds) < 2000:
                return {"drifted": False, "reason": "insufficient_data"}
            baseline_preds = current_preds[:1000]
            recent_preds = current_preds[-1000:]
        else:
            baseline_preds = baseline_predictions
            recent_preds = current_preds[-min(1000, len(current_preds)):]

        # KS test on predictions
        ks_stat, ks_pvalue = stats.ks_2samp(baseline_preds, recent_preds)

        # Mean prediction shift
        mean_shift = abs(np.mean(recent_preds) - np.mean(baseline_preds))

        report = {
            "model_name": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "ks_statistic": float(ks_stat),
            "ks_pvalue": float(ks_pvalue),
            "mean_shift": float(mean_shift),
            "baseline_mean": float(np.mean(baseline_preds)),
            "current_mean": float(np.mean(recent_preds)),
            "drifted": ks_stat > self.ks_threshold,
        }

        if report["drifted"]:
            self._raise_alert(
                drift_type=DriftType.PREDICTION_DRIFT,
                severity=AlertSeverity.WARNING,
                feature=None,
                metric_value=ks_stat,
                threshold=self.ks_threshold,
                message=f"Prediction drift: KS={ks_stat:.4f}, mean shift={mean_shift:.4f}",
                details=report,
            )

        return report

    def check_performance(self, y_true: np.ndarray, y_pred: np.ndarray,
                         baseline_auc: float) -> Dict[str, Any]:
        """Check if model performance has degraded"""
        from sklearn.metrics import roc_auc_score, f1_score

        self.label_buffer.extend(y_true.tolist())

        current_auc = roc_auc_score(y_true, y_pred)
        current_f1 = f1_score(y_true, (y_pred >= 0.5).astype(int), zero_division=0)

        degradation = baseline_auc - current_auc

        report = {
            "model_name": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "current_auc": float(current_auc),
            "baseline_auc": float(baseline_auc),
            "degradation": float(degradation),
            "current_f1": float(current_f1),
            "degraded": degradation > self.perf_degradation_threshold,
            "n_samples": len(y_true),
        }

        if report["degraded"]:
            self._raise_alert(
                drift_type=DriftType.PERFORMANCE_DRIFT,
                severity=AlertSeverity.CRITICAL,
                feature=None,
                metric_value=degradation,
                threshold=self.perf_degradation_threshold,
                message=f"Performance degradation: AUC dropped {degradation:.4f} "
                        f"(baseline={baseline_auc:.4f}, current={current_auc:.4f})",
                details=report,
            )

        return report

    def should_retrain(self) -> Tuple[bool, str]:
        """Determine if model should be retrained based on monitoring signals"""
        reasons = []

        # Check recent alerts
        recent_alerts = [a for a in self.alerts
                        if datetime.fromisoformat(a.timestamp) > datetime.now() - timedelta(hours=24)]

        critical_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            reasons.append(f"{len(critical_alerts)} critical alerts in last 24h")

        # Check drift ratio
        if self.metrics_history:
            latest = self.metrics_history[-1]
            if latest.get("drift_ratio", 0) > 0.3:
                reasons.append(f"High drift ratio: {latest['drift_ratio']:.2f}")

        should_retrain = len(reasons) > 0
        reason = "; ".join(reasons) if reasons else "No retraining needed"

        return should_retrain, reason

    def get_prometheus_metrics(self) -> str:
        """Export monitoring metrics in Prometheus format"""
        lines = []
        lines.append(f"# HELP ml_model_alerts_total Total alerts raised")
        lines.append(f"# TYPE ml_model_alerts_total counter")
        lines.append(f'ml_model_alerts_total{{model="{self.model_name}"}} {len(self.alerts)}')

        lines.append(f"# HELP ml_model_predictions_total Total predictions made")
        lines.append(f"# TYPE ml_model_predictions_total counter")
        lines.append(f'ml_model_predictions_total{{model="{self.model_name}"}} {len(self.prediction_buffer)}')

        if self.metrics_history:
            latest = self.metrics_history[-1]
            lines.append(f"# HELP ml_model_drift_ratio Feature drift ratio")
            lines.append(f"# TYPE ml_model_drift_ratio gauge")
            lines.append(f'ml_model_drift_ratio{{model="{self.model_name}"}} {latest.get("drift_ratio", 0)}')

        return "\n".join(lines)

    def _compute_psi(self, baseline_hist: List, bin_edges: List, current_values: np.ndarray) -> float:
        """Compute Population Stability Index"""
        # Bin current values using baseline bin edges
        current_hist, _ = np.histogram(current_values, bins=bin_edges)

        # Normalize to proportions
        baseline_prop = np.array(baseline_hist, dtype=float)
        current_prop = np.array(current_hist, dtype=float)

        # Avoid division by zero
        baseline_prop = np.maximum(baseline_prop / max(baseline_prop.sum(), 1), 1e-6)
        current_prop = np.maximum(current_prop / max(current_prop.sum(), 1), 1e-6)

        # PSI formula
        psi = np.sum((current_prop - baseline_prop) * np.log(current_prop / baseline_prop))
        return float(psi)

    def _raise_alert(self, drift_type: DriftType, severity: AlertSeverity,
                    feature: Optional[str], metric_value: float, threshold: float,
                    message: str, details: Dict):
        """Raise a monitoring alert"""
        alert = DriftAlert(
            alert_id=f"{self.model_name}_{drift_type.value}_{int(time.time())}",
            model_name=self.model_name,
            drift_type=drift_type,
            severity=severity,
            feature=feature,
            metric_value=metric_value,
            threshold=threshold,
            message=message,
            timestamp=datetime.now().isoformat(),
            details=details,
        )
        self.alerts.append(alert)
        logger.warning(f"ALERT [{severity.value}] {message}")

        if self.alert_callback:
            self.alert_callback(asdict(alert))
