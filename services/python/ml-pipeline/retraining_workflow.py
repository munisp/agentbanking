#!/usr/bin/env python3
"""
Automated Retraining Workflow — Temporal-based orchestration

Implements the full production retraining cycle:
1. Monitor → Detect drift or scheduled trigger
2. Ingest → Pull new data from production PostgreSQL via Lakehouse
3. Retrain → Continue training from existing weights
4. Evaluate → Compare new model against champion
5. Register → Version new model in registry
6. A/B Test → Canary deploy (80/20 split)
7. Promote → If challenger wins, promote to production

Can be triggered by:
- Scheduled cron (daily/weekly)
- Drift detection alert (PSI > threshold)
- Manual trigger (API call)
- Data volume threshold (N new transactions since last training)

Usage:
    # Run as standalone workflow
    python retraining_workflow.py --trigger scheduled --db-url postgresql://...

    # Run drift-triggered retraining
    python retraining_workflow.py --trigger drift --db-url postgresql://...

    # Dry run (evaluate only, don't register/deploy)
    python retraining_workflow.py --trigger scheduled --dry-run
"""

import sys
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from continue_training import ContinualTrainer, MODELS_DIR, REGISTRY_DIR, LAKEHOUSE_DIR
from monitoring.model_monitor import ModelMonitor
from registry.model_registry import ModelRegistry, ModelStage
from ab_testing.ab_test_manager import ABTestManager
from lakehouse.delta_lake_store import DeltaLakeStore


class RetrainingTrigger(str, Enum):
    SCHEDULED = "scheduled"        # Cron-based (daily, weekly)
    DRIFT = "drift"                # PSI threshold exceeded
    VOLUME = "volume"              # N new transactions
    MANUAL = "manual"              # API/CLI trigger
    PERFORMANCE = "performance"    # Model performance degradation


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    TRAINING = "training"
    EVALUATING = "evaluating"
    REGISTERING = "registering"
    AB_TESTING = "ab_testing"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RetrainingConfig:
    """Configuration for a retraining run"""
    trigger: RetrainingTrigger = RetrainingTrigger.SCHEDULED
    db_url: Optional[str] = None
    min_new_samples: int = 10000
    improvement_threshold: float = 0.005
    lr_multiplier: float = 0.1
    canary_split: float = 0.2
    ab_test_min_samples: int = 1000
    ab_test_confidence: float = 0.95
    max_retrain_time_seconds: int = 600
    models_to_train: List[str] = None
    dry_run: bool = False

    def __post_init__(self):
        if self.models_to_train is None:
            self.models_to_train = ["fraud", "gnn", "credit"]


@dataclass
class WorkflowResult:
    """Result of a retraining workflow execution"""
    workflow_id: str
    trigger: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    data_ingested: int = 0
    models_trained: int = 0
    models_improved: int = 0
    models_promoted: int = 0
    ab_experiment_id: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict] = None


class RetrainingWorkflow:
    """
    Production retraining workflow orchestrator.

    In production, this would be a Temporal workflow with activities.
    The code is structured to be easily converted to Temporal activities:
    - Each method is an activity
    - State is passed between activities via the workflow
    - Retries and timeouts are handled per-activity

    For now, runs as a sequential Python script with the same semantics.
    """

    def __init__(self, config: RetrainingConfig):
        self.config = config
        self.workflow_id = f"retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{config.trigger.value}"
        self.status = WorkflowStatus.PENDING
        self.result = WorkflowResult(
            workflow_id=self.workflow_id,
            trigger=config.trigger.value,
            status=self.status.value,
            started_at=datetime.now().isoformat(),
        )

    def execute(self) -> WorkflowResult:
        """Execute the full retraining workflow"""
        start_time = time.time()

        try:
            logger.info("=" * 70)
            logger.info(f"RETRAINING WORKFLOW: {self.workflow_id}")
            logger.info(f"Trigger: {self.config.trigger.value}")
            logger.info("=" * 70)

            # Activity 1: Check if retraining is needed
            should_retrain, reason = self._activity_check_retraining_needed()
            if not should_retrain:
                logger.info(f"Skipping retraining: {reason}")
                self.result.status = WorkflowStatus.SKIPPED.value
                self.result.details = {"skip_reason": reason}
                return self.result

            logger.info(f"Retraining triggered: {reason}")

            # Activity 2: Ingest new data
            self.status = WorkflowStatus.INGESTING
            new_data = self._activity_ingest_data()
            self.result.data_ingested = len(new_data.get("transactions", []))

            if self.result.data_ingested < self.config.min_new_samples:
                logger.info(f"Insufficient data: {self.result.data_ingested} < {self.config.min_new_samples}")
                self.result.status = WorkflowStatus.SKIPPED.value
                self.result.details = {"skip_reason": "insufficient_data"}
                return self.result

            # Activity 3: Continue training
            self.status = WorkflowStatus.TRAINING
            training_summary = self._activity_continue_training(new_data)
            self.result.models_trained = training_summary.get("models_trained", 0)
            self.result.models_improved = training_summary.get("models_improved", 0)

            # Activity 4: Evaluate and decide
            self.status = WorkflowStatus.EVALUATING
            improved_models = training_summary.get("models_registered", [])

            if not improved_models:
                logger.info("No models improved above threshold — workflow complete (no promotion)")
                self.result.status = WorkflowStatus.COMPLETED.value
                self.result.details = {"outcome": "no_improvement"}
                return self.result

            # Activity 5: Register (already done in continue_training)
            self.status = WorkflowStatus.REGISTERING
            self.result.models_promoted = 0

            # Activity 6: A/B Test setup
            if not self.config.dry_run:
                self.status = WorkflowStatus.AB_TESTING
                ab_id = training_summary.get("ab_experiment_id")
                self.result.ab_experiment_id = ab_id
                logger.info(f"A/B test active: {ab_id}")

            # Done
            self.status = WorkflowStatus.COMPLETED
            self.result.status = WorkflowStatus.COMPLETED.value
            self.result.details = {
                "outcome": "ab_test_started" if not self.config.dry_run else "dry_run_complete",
                "improved_models": improved_models,
                "training_summary": training_summary,
            }

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            self.result.status = WorkflowStatus.FAILED.value
            self.result.error = str(e)
            logger.error(f"Workflow failed: {e}", exc_info=True)

        finally:
            self.result.completed_at = datetime.now().isoformat()
            self.result.duration_seconds = time.time() - start_time
            self._save_workflow_result()

        return self.result

    def _activity_check_retraining_needed(self) -> tuple:
        """Activity: Determine if retraining should proceed"""
        if self.config.trigger == RetrainingTrigger.MANUAL:
            return True, "Manual trigger"

        if self.config.trigger == RetrainingTrigger.SCHEDULED:
            return True, "Scheduled retraining"

        if self.config.trigger == RetrainingTrigger.DRIFT:
            return self._check_drift_trigger()

        if self.config.trigger == RetrainingTrigger.VOLUME:
            return self._check_volume_trigger()

        if self.config.trigger == RetrainingTrigger.PERFORMANCE:
            return self._check_performance_trigger()

        return True, "Unknown trigger — proceeding"

    def _check_drift_trigger(self) -> tuple:
        """Check if data drift exceeds threshold"""
        try:
            import pandas as pd
            lakehouse = DeltaLakeStore(root_path=str(LAKEHOUSE_DIR))

            # Load baseline and recent data
            baseline_path = Path(LAKEHOUSE_DIR) / "fraud_transactions"
            if not baseline_path.exists():
                return True, "No baseline data — first training"

            baseline_df = pd.read_parquet(str(baseline_path))
            monitor_cols = ["amount_ngn", "fee_ngn", "ip_risk_score",
                           "session_duration_sec", "distance_from_usual_km"]

            available_cols = [c for c in monitor_cols if c in baseline_df.columns]
            if not available_cols:
                return True, "Cannot check drift — missing columns"

            monitor = ModelMonitor("fraud_ensemble", baseline_data=baseline_df[available_cols])
            drift_result = monitor.check_data_drift(baseline_df[available_cols].tail(1000))

            if drift_result.get("overall_drifted", False):
                return True, f"Drift detected (ratio={drift_result.get('drift_ratio', 0):.2f})"
            return False, f"No significant drift (ratio={drift_result.get('drift_ratio', 0):.2f})"

        except Exception as e:
            logger.warning(f"Drift check failed: {e}")
            return True, f"Drift check error — retraining as precaution"

    def _check_volume_trigger(self) -> tuple:
        """Check if enough new data has accumulated"""
        try:
            summary_path = MODELS_DIR / "training_summary.json"
            if not summary_path.exists():
                return True, "No previous training — first run"

            with open(summary_path) as f:
                last_summary = json.load(f)

            last_count = last_summary.get("data_config", {}).get("n_transactions", 0)
            # In production, compare against live DB count
            return True, f"Volume trigger — last training on {last_count} transactions"

        except Exception as e:
            return True, f"Volume check error: {e}"

    def _check_performance_trigger(self) -> tuple:
        """Check if model performance has degraded"""
        try:
            registry = ModelRegistry(registry_path=str(REGISTRY_DIR))
            models = registry.list_models()

            for m in models:
                metrics = m.get("metrics", {})
                if metrics.get("auc", 1) < 0.55:
                    return True, f"Performance degradation: {m['model_name']} AUC={metrics.get('auc'):.4f}"

            return False, "All models within acceptable performance"

        except Exception as e:
            return True, f"Performance check error: {e}"

    def _activity_ingest_data(self) -> Dict[str, Any]:
        """Activity: Ingest new training data"""
        trainer = ContinualTrainer(
            models_dir=MODELS_DIR,
            lr_multiplier=self.config.lr_multiplier,
            improvement_threshold=self.config.improvement_threshold,
        )

        if self.config.db_url:
            return trainer.ingest_new_data(mode="production", db_url=self.config.db_url)
        else:
            # Fallback to synthetic with time-based seed for variety
            return trainer.ingest_new_data(
                mode="synthetic",
                n_transactions=50000,
                seed=int(time.time()) % 100000,
            )

    def _activity_continue_training(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Activity: Run continue training"""
        trainer = ContinualTrainer(
            models_dir=MODELS_DIR,
            lr_multiplier=self.config.lr_multiplier,
            improvement_threshold=self.config.improvement_threshold,
        )

        summary = trainer.run(
            mode="synthetic" if not self.config.db_url else "production",
            models=self.config.models_to_train,
            db_url=self.config.db_url,
            skip_ab_test=self.config.dry_run,
        )

        return summary

    def _save_workflow_result(self):
        """Persist workflow result for auditing"""
        results_dir = Path(MODELS_DIR).parent / "workflow_history"
        results_dir.mkdir(parents=True, exist_ok=True)

        result_path = results_dir / f"{self.workflow_id}.json"
        with open(result_path, "w") as f:
            json.dump(asdict(self.result), f, indent=2, default=str)

        logger.info(f"Workflow result saved: {result_path}")


class ScheduledRetrainingManager:
    """
    Manages scheduled retraining jobs.

    In production, this integrates with:
    - Temporal: Cron-scheduled workflow executions
    - Kafka: Drift alert event consumption
    - FastAPI: Manual trigger endpoint

    For now, provides the scheduling logic and state management.
    """

    def __init__(self, schedule_config: Dict[str, Any] = None):
        self.schedule_config = schedule_config or {
            "daily_retrain_hour": 2,  # 2 AM UTC
            "weekly_full_retrain_day": 0,  # Monday
            "drift_check_interval_hours": 6,
            "min_hours_between_retrains": 12,
        }
        self.history_dir = Path(MODELS_DIR).parent / "workflow_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def should_run_scheduled(self) -> tuple:
        """Check if a scheduled retraining should run now"""
        now = datetime.now()
        last_run = self._get_last_successful_run()

        if last_run is None:
            return True, "No previous successful run"

        hours_since_last = (now - last_run).total_seconds() / 3600
        if hours_since_last < self.schedule_config["min_hours_between_retrains"]:
            return False, f"Too recent: {hours_since_last:.1f}h since last run"

        # Check if it's the scheduled hour
        if now.hour == self.schedule_config["daily_retrain_hour"]:
            if now.weekday() == self.schedule_config["weekly_full_retrain_day"]:
                return True, "Weekly full retrain"
            return True, "Daily incremental retrain"

        return False, "Not scheduled time"

    def _get_last_successful_run(self) -> Optional[datetime]:
        """Get timestamp of last successful retraining"""
        if not self.history_dir.exists():
            return None

        history_files = sorted(self.history_dir.glob("retrain_*.json"), reverse=True)
        for f in history_files:
            try:
                with open(f) as fp:
                    result = json.load(fp)
                if result.get("status") == "completed":
                    return datetime.fromisoformat(result["completed_at"])
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def get_retraining_history(self, limit: int = 10) -> List[Dict]:
        """Get recent retraining history"""
        history = []
        history_files = sorted(self.history_dir.glob("retrain_*.json"), reverse=True)

        for f in history_files[:limit]:
            try:
                with open(f) as fp:
                    history.append(json.load(fp))
            except json.JSONDecodeError:
                continue

        return history

    def run_if_needed(self, config: RetrainingConfig = None) -> Optional[WorkflowResult]:
        """Check schedule and run if needed"""
        should_run, reason = self.should_run_scheduled()
        if not should_run:
            logger.info(f"Scheduled retraining not needed: {reason}")
            return None

        logger.info(f"Running scheduled retraining: {reason}")
        config = config or RetrainingConfig(trigger=RetrainingTrigger.SCHEDULED)
        workflow = RetrainingWorkflow(config)
        return workflow.execute()


# ======================== Temporal Integration Stubs ========================
# These would be Temporal activities in production

def temporal_activity_check_drift():
    """Temporal activity: Check data drift"""
    import pandas as pd
    from monitoring.model_monitor import ModelMonitor

    baseline_path = Path(LAKEHOUSE_DIR) / "fraud_transactions"
    if not baseline_path.exists():
        return {"should_retrain": True, "reason": "no_baseline"}

    df = pd.read_parquet(str(baseline_path))
    monitor_cols = ["amount_ngn", "fee_ngn", "ip_risk_score",
                    "session_duration_sec", "distance_from_usual_km"]
    available_cols = [c for c in monitor_cols if c in df.columns]

    monitor = ModelMonitor("fraud_ensemble", baseline_data=df[available_cols])
    result = monitor.check_data_drift(df[available_cols].sample(min(1000, len(df))))

    return {
        "should_retrain": result.get("overall_drifted", False),
        "drift_ratio": result.get("drift_ratio", 0),
        "reason": "drift_detected" if result.get("overall_drifted") else "no_drift",
    }


def temporal_activity_ingest(db_url: str, table: str, incremental_col: str = None):
    """Temporal activity: Ingest new data from production"""
    lakehouse = DeltaLakeStore(root_path=str(LAKEHOUSE_DIR))
    return lakehouse.ingest_from_postgres(
        connection_url=db_url,
        query=f"SELECT * FROM {table}",
        table_name=f"{table}_incremental",
        incremental_column=incremental_col,
    )


def temporal_activity_retrain(mode: str, db_url: str = None, lr_multiplier: float = 0.1):
    """Temporal activity: Run continue training"""
    trainer = ContinualTrainer(lr_multiplier=lr_multiplier)
    return trainer.run(mode=mode, db_url=db_url)


def temporal_activity_promote(model_name: str, version: int, reason: str):
    """Temporal activity: Promote model to production"""
    registry = ModelRegistry(registry_path=str(REGISTRY_DIR))
    registry.promote_model(model_name, version, ModelStage.PRODUCTION, reason=reason)
    return {"promoted": model_name, "version": version}


# ======================== CLI ========================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run retraining workflow")
    parser.add_argument("--trigger", choices=["scheduled", "drift", "volume", "manual", "performance"],
                       default="manual", help="Retraining trigger type")
    parser.add_argument("--db-url", type=str, help="PostgreSQL connection URL")
    parser.add_argument("--lr-multiplier", type=float, default=0.1,
                       help="Learning rate multiplier for fine-tuning")
    parser.add_argument("--improvement-threshold", type=float, default=0.005,
                       help="Min AUC improvement to register")
    parser.add_argument("--models", nargs="+", default=["fraud", "gnn", "credit"],
                       help="Model types to retrain")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate only, don't register/deploy")
    parser.add_argument("--history", action="store_true", help="Show retraining history")

    args = parser.parse_args()

    if args.history:
        manager = ScheduledRetrainingManager()
        history = manager.get_retraining_history()
        print(json.dumps(history, indent=2))
        return

    config = RetrainingConfig(
        trigger=RetrainingTrigger(args.trigger),
        db_url=args.db_url,
        lr_multiplier=args.lr_multiplier,
        improvement_threshold=args.improvement_threshold,
        models_to_train=args.models,
        dry_run=args.dry_run,
    )

    workflow = RetrainingWorkflow(config)
    result = workflow.execute()

    print(f"\nWorkflow Result:")
    print(f"  Status: {result.status}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Models trained: {result.models_trained}")
    print(f"  Models improved: {result.models_improved}")
    if result.ab_experiment_id:
        print(f"  A/B test: {result.ab_experiment_id}")
    if result.error:
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    main()
