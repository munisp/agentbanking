#!/usr/bin/env python3
"""
Master Training Script — Trains All ML/DL/GNN Models

This script supports two modes:
A) Fresh training (default) — trains from scratch on generated synthetic data
B) Continue training (--resume-from) — loads existing weights and fine-tunes on new data

Fresh training:
1. Generates realistic Nigerian synthetic training data
2. Trains fraud detection models (XGBoost, LightGBM, RF, DNN, IsolationForest)
3. Trains GNN models (GCN, GAT, GraphSAGE) on transaction graphs
4. Trains credit scoring models (XGBoost, LightGBM, DNN)
5. Stores training data in Lakehouse (Delta Lake)
6. Registers all models in the model registry
7. Persists weights to disk (.pt, .joblib files)

Continue training:
1. Loads existing model weights from --resume-from directory
2. Generates or ingests new training data
3. Fine-tunes PyTorch models with lower LR (--lr-multiplier)
4. Uses warm_start for XGBoost/LightGBM (incremental boosting)
5. Evaluates improvement, registers new version if above threshold
6. Sets up A/B test (champion vs challenger)

Usage:
    # Fresh training
    python train_all_models.py
    python train_all_models.py --n-transactions 500000 --n-customers 50000

    # Continue training from existing weights
    python train_all_models.py --resume-from models/weights --n-transactions 50000
    python train_all_models.py --resume-from models/weights --lr-multiplier 0.05

    # Continue training from production data
    python continue_training.py --mode production --db-url postgresql://...

Output:
    models/weights/  - All trained model weight files
    models/registry/ - Model versioning metadata
"""

import argparse
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from data_generator.nigerian_synthetic_data import generate_training_dataset, DataConfig, NigerianTransactionGenerator
from training.fraud_detection_trainer import FraudDetectionTrainer
from training.gnn_trainer import GNNFraudTrainer
from training.credit_scoring_trainer import CreditScoringTrainer
from lakehouse.delta_lake_store import DeltaLakeStore
from registry.model_registry import ModelRegistry, ModelType, ModelStage
from monitoring.model_monitor import ModelMonitor


MODELS_DIR = Path(__file__).parent / "models" / "weights"


def main():
    parser = argparse.ArgumentParser(description="Train all ML models for 54agent platform")
    parser.add_argument("--n-transactions", type=int, default=200_000,
                       help="Number of synthetic transactions to generate")
    parser.add_argument("--n-customers", type=int, default=20_000,
                       help="Number of synthetic customers")
    parser.add_argument("--n-agents", type=int, default=1_000,
                       help="Number of synthetic agents")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-gnn", action="store_true", help="Skip GNN training")
    parser.add_argument("--output-dir", type=str, default=str(MODELS_DIR),
                       help="Output directory for model weights")
    # Continue training arguments
    parser.add_argument("--resume-from", type=str, default=None,
                       help="Path to existing weights directory to resume training from")
    parser.add_argument("--lr-multiplier", type=float, default=0.1,
                       help="Learning rate multiplier for continue training (default: 0.1 = 10%% of original)")
    parser.add_argument("--improvement-threshold", type=float, default=0.005,
                       help="Min AUC improvement to register new model version")
    args = parser.parse_args()

    # If --resume-from is provided, delegate to continue_training module
    if args.resume_from:
        from continue_training import ContinualTrainer
        logger.info("=" * 70)
        logger.info("54agent ML PIPELINE — CONTINUE TRAINING (--resume-from)")
        logger.info("=" * 70)
        logger.info(f"Resuming from: {args.resume_from}")
        logger.info(f"LR multiplier: {args.lr_multiplier}")
        logger.info(f"New data: {args.n_transactions} synthetic transactions")

        trainer = ContinualTrainer(
            models_dir=Path(args.resume_from),
            lr_multiplier=args.lr_multiplier,
            improvement_threshold=args.improvement_threshold,
        )
        summary = trainer.run(
            mode="synthetic",
            models=["fraud", "credit"] if args.skip_gnn else ["fraud", "gnn", "credit"],
            n_transactions=args.n_transactions,
            seed=args.seed if args.seed != 42 else None,
        )
        logger.info(f"\nContinue training complete: {summary['models_improved']}/{summary['models_trained']} improved")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("54agent ML PIPELINE — FULL MODEL TRAINING")
    logger.info("=" * 70)
    logger.info(f"Config: {args.n_transactions} transactions, {args.n_customers} customers, "
                f"{args.n_agents} agents")
    logger.info(f"Output: {output_dir}")
    overall_start = time.time()

    # ===== Step 1: Generate Synthetic Data =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 1: Generating Nigerian Synthetic Data")
    logger.info("=" * 50)

    data = generate_training_dataset(
        n_transactions=args.n_transactions,
        n_customers=args.n_customers,
        n_agents=args.n_agents,
        seed=args.seed,
    )

    transactions = data["transactions"]
    credit_data = data["credit_data"]
    graph_data = data["graph_data"]

    logger.info(f"Generated: {len(transactions)} transactions, {len(credit_data)} credit records")
    logger.info(f"Graph: {graph_data['node_features'].shape[0]} nodes, {graph_data['edge_index'].shape[1]} edges")

    # ===== Step 2: Store in Lakehouse =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 2: Storing Data in Lakehouse")
    logger.info("=" * 50)

    lakehouse = DeltaLakeStore(root_path=str(output_dir.parent / "lakehouse"))
    lakehouse.write_training_data(transactions, "fraud_transactions", version_tag="v1.0")
    lakehouse.write_training_data(credit_data, "credit_features", version_tag="v1.0")

    # ===== Step 3: Train Fraud Detection Models =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 3: Training Fraud Detection Models")
    logger.info("=" * 50)

    fraud_trainer = FraudDetectionTrainer(output_dir=output_dir)
    fraud_results = fraud_trainer.train_all(transactions)

    # ===== Step 4: Train GNN Models =====
    if not args.skip_gnn:
        logger.info("\n" + "=" * 50)
        logger.info("STEP 4: Training GNN Models")
        logger.info("=" * 50)

        gnn_trainer = GNNFraudTrainer(output_dir=output_dir)
        gnn_results = gnn_trainer.train_all(graph_data)
    else:
        logger.info("\nStep 4: Skipped GNN training (--skip-gnn)")
        gnn_results = {}

    # ===== Step 5: Train Credit Scoring Models =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 5: Training Credit Scoring Models")
    logger.info("=" * 50)

    credit_trainer = CreditScoringTrainer(output_dir=output_dir)
    credit_results = credit_trainer.train_all(credit_data)

    # ===== Step 6: Register Models =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 6: Registering Models")
    logger.info("=" * 50)

    registry = ModelRegistry(registry_path=str(output_dir.parent / "registry"))

    # Register fraud models
    for model_name, metrics in fraud_results.items():
        artifact_name = f"fraud_{model_name}"
        # Find the artifact file
        for ext in [".joblib", "_best.pt"]:
            artifact_path = output_dir / f"{artifact_name}{ext}"
            if artifact_path.exists():
                meta = registry.register_model(
                    model_name=artifact_name,
                    model_type=ModelType.FRAUD_DETECTION,
                    artifact_path=str(artifact_path),
                    metrics=metrics,
                    description=f"Fraud detection model ({model_name})",
                    tags={"dataset": "nigerian_synthetic_v1", "framework": "sklearn" if "forest" in model_name or "gb" in model_name else "pytorch"},
                )
                # Promote to production
                registry.promote_model(artifact_name, meta["version"], ModelStage.PRODUCTION,
                                      reason="Initial training on synthetic data")
                break

    # Register GNN models
    for model_name, metrics in gnn_results.items():
        artifact_name = f"fraud_{model_name}"
        artifact_path = output_dir / f"{artifact_name}_best.pt"
        if artifact_path.exists():
            meta = registry.register_model(
                model_name=artifact_name,
                model_type=ModelType.GNN_FRAUD,
                artifact_path=str(artifact_path),
                metrics=metrics,
                description=f"GNN fraud detection ({model_name})",
                tags={"dataset": "nigerian_synthetic_v1", "framework": "pytorch_geometric"},
            )
            registry.promote_model(artifact_name, meta["version"], ModelStage.PRODUCTION,
                                  reason="Initial GNN training")

    # Register credit models
    for model_name, metrics in credit_results.items():
        artifact_name = f"credit_{model_name}" if not model_name.startswith("credit_") else model_name
        for ext in [".joblib", "_best.pt"]:
            candidate = f"credit_{model_name}{ext}" if not model_name.startswith("credit_") else f"{model_name}{ext}"
            artifact_path = output_dir / candidate
            if artifact_path.exists():
                meta = registry.register_model(
                    model_name=artifact_name,
                    model_type=ModelType.CREDIT_SCORING,
                    artifact_path=str(artifact_path),
                    metrics=metrics,
                    description=f"Credit scoring model ({model_name})",
                    tags={"dataset": "nigerian_synthetic_v1"},
                )
                registry.promote_model(artifact_name, meta["version"], ModelStage.PRODUCTION,
                                      reason="Initial credit scoring training")
                break

    # ===== Step 7: Setup Monitoring Baselines =====
    logger.info("\n" + "=" * 50)
    logger.info("STEP 7: Setting Up Monitoring Baselines")
    logger.info("=" * 50)

    monitor = ModelMonitor("fraud_ensemble", baseline_data=transactions[
        ["amount_ngn", "fee_ngn", "ip_risk_score", "session_duration_sec", "distance_from_usual_km"]
    ])
    logger.info("Monitoring baseline configured")

    # ===== Summary =====
    total_time = time.time() - overall_start
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING COMPLETE — SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f}min)")
    logger.info(f"\nFraud Detection Models:")
    for name, metrics in fraud_results.items():
        logger.info(f"  {name}: AUC={metrics.get('auc', 'N/A'):.4f}, F1={metrics.get('f1', 'N/A'):.4f}")

    if gnn_results:
        logger.info(f"\nGNN Models:")
        for name, metrics in gnn_results.items():
            logger.info(f"  {name}: AUC={metrics.get('auc', 'N/A'):.4f}, F1={metrics.get('f1', 'N/A'):.4f}")

    logger.info(f"\nCredit Scoring Models:")
    for name, metrics in credit_results.items():
        if "rmse" in metrics:
            logger.info(f"  {name}: RMSE={metrics['rmse']:.2f}, R²={metrics['r2']:.4f}")
        else:
            logger.info(f"  {name}: AUC={metrics.get('auc', 'N/A'):.4f}")

    # List weight files
    weight_files = list(output_dir.glob("*"))
    logger.info(f"\nWeight files saved ({len(weight_files)}):")
    for wf in sorted(weight_files):
        size_kb = wf.stat().st_size / 1024
        logger.info(f"  {wf.name} ({size_kb:.1f} KB)")

    # Save overall summary
    summary = {
        "training_timestamp": datetime.now().isoformat(),
        "total_duration_seconds": total_time,
        "data_config": {
            "n_transactions": args.n_transactions,
            "n_customers": args.n_customers,
            "n_agents": args.n_agents,
            "seed": args.seed,
        },
        "fraud_results": {k: {mk: float(mv) for mk, mv in v.items() if isinstance(mv, (int, float))} for k, v in fraud_results.items()},
        "gnn_results": {k: {mk: float(mv) for mk, mv in v.items() if isinstance(mv, (int, float))} for k, v in gnn_results.items()},
        "credit_results": {k: {mk: float(mv) for mk, mv in v.items() if isinstance(mv, (int, float))} for k, v in credit_results.items()},
        "weight_files": [wf.name for wf in sorted(weight_files)],
    }
    with open(output_dir / "training_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"\nAll models saved to: {output_dir}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
