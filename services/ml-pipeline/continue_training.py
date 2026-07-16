#!/usr/bin/env python3
"""
Continue Training Script — Incrementally retrain models on new platform data

This script implements continual learning:
1. Loads existing trained model weights from disk
2. Ingests new data from production PostgreSQL (via Lakehouse) or new files
3. Fine-tunes PyTorch models (DNN, GNN) with lower learning rate
4. Uses warm_start for XGBoost/LightGBM for incremental tree boosting
5. Evaluates new model against old model
6. Registers new version if improvement threshold met
7. Optionally sets up A/B test (new vs old)

Usage:
    # Continue training from existing weights with new synthetic data
    python continue_training.py --mode synthetic --n-transactions 50000

    # Continue training from production database
    python continue_training.py --mode production --db-url postgresql://user:pass@host/db

    # Continue training from a Parquet file
    python continue_training.py --mode file --data-path /path/to/new_transactions.parquet

    # Only retrain specific model types
    python continue_training.py --mode synthetic --models fraud credit

    # Fine-tune with custom learning rate multiplier
    python continue_training.py --mode synthetic --lr-multiplier 0.1
"""

import argparse
import sys
import time
import json
import logging
import numpy as np
import pandas as pd
import torch
import joblib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from data_generator.nigerian_synthetic_data import generate_training_dataset
from training.fraud_detection_trainer import FraudDetectionTrainer, FraudDetectionDNN, FraudFeatureEngineer
from training.gnn_trainer import GNNFraudTrainer, FraudGCN, FraudGAT, FraudGraphSAGE
from training.credit_scoring_trainer import CreditScoringTrainer
from lakehouse.delta_lake_store import DeltaLakeStore
from registry.model_registry import ModelRegistry, ModelType, ModelStage
from monitoring.model_monitor import ModelMonitor
from ab_testing.ab_test_manager import ABTestManager


MODELS_DIR = Path(__file__).parent / "models" / "weights"
REGISTRY_DIR = Path(__file__).parent / "models" / "registry"
LAKEHOUSE_DIR = Path(__file__).parent / "models" / "lakehouse"


class ContinualTrainer:
    """Orchestrates continual/incremental training from existing weights"""

    def __init__(
        self,
        models_dir: Path = MODELS_DIR,
        registry_dir: Path = REGISTRY_DIR,
        lakehouse_dir: Path = LAKEHOUSE_DIR,
        lr_multiplier: float = 0.1,
        improvement_threshold: float = 0.005,
        device: str = None,
    ):
        self.models_dir = models_dir
        self.registry = ModelRegistry(registry_path=str(registry_dir))
        self.lakehouse = DeltaLakeStore(root_path=str(lakehouse_dir))
        self.lr_multiplier = lr_multiplier
        self.improvement_threshold = improvement_threshold
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        self.old_metrics: Dict[str, Dict] = {}
        self.new_metrics: Dict[str, Dict] = {}
        self.improved_models: List[str] = []
        self.training_log: List[Dict] = []

    def load_existing_weights(self) -> Dict[str, Any]:
        """Load all existing model weights and metadata"""
        loaded = {}

        # Load sklearn/XGBoost/LightGBM models
        joblib_files = list(self.models_dir.glob("*.joblib"))
        for f in joblib_files:
            name = f.stem
            if "feature_engineer" not in name:
                model = joblib.load(f)
                loaded[name] = {"model": model, "type": "sklearn", "path": f}
                logger.info(f"  Loaded existing weights: {name}")

        # Load PyTorch models
        pt_files = list(self.models_dir.glob("*.pt"))
        for f in pt_files:
            name = f.stem
            checkpoint = torch.load(f, map_location=self.device)
            loaded[name] = {"checkpoint": checkpoint, "type": "pytorch", "path": f}
            logger.info(f"  Loaded existing checkpoint: {name}")

        # Load feature engineers
        fe_fraud_path = self.models_dir / "fraud_feature_engineer.joblib"
        fe_credit_path = self.models_dir / "credit_feature_engineer.joblib"
        if fe_fraud_path.exists():
            loaded["fraud_feature_engineer"] = joblib.load(fe_fraud_path)
        if fe_credit_path.exists():
            loaded["credit_feature_engineer"] = joblib.load(fe_credit_path)

        return loaded

    def ingest_new_data(
        self,
        mode: str,
        db_url: str = None,
        data_path: str = None,
        n_transactions: int = 50000,
        n_customers: int = 5000,
        n_agents: int = 500,
        seed: int = None,
    ) -> Dict[str, Any]:
        """Ingest new training data from various sources"""
        logger.info(f"Ingesting new data (mode={mode})")

        if mode == "production":
            return self._ingest_from_production(db_url)
        elif mode == "file":
            return self._ingest_from_file(data_path)
        elif mode == "synthetic":
            return self._ingest_synthetic(n_transactions, n_customers, n_agents, seed)
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'production', 'file', or 'synthetic'")

    def _ingest_from_production(self, db_url: str) -> Dict[str, Any]:
        """Ingest new data from production PostgreSQL"""
        if not db_url:
            raise ValueError("--db-url required for production mode")

        # Ingest fraud transactions incrementally
        fraud_meta = self.lakehouse.ingest_from_postgres(
            connection_url=db_url,
            query="SELECT * FROM transactions",
            table_name="fraud_transactions_incremental",
            incremental_column="created_at",
            last_value=self._get_last_ingestion_timestamp("fraud_transactions"),
        )

        # Ingest credit data
        credit_meta = self.lakehouse.ingest_from_postgres(
            connection_url=db_url,
            query="SELECT * FROM customer_credit_profiles",
            table_name="credit_features_incremental",
            incremental_column="updated_at",
            last_value=self._get_last_ingestion_timestamp("credit_features"),
        )

        # Read back as DataFrames
        transactions = pd.read_parquet(
            str(Path(self.lakehouse.root_path) / "fraud_transactions_incremental")
        )
        credit_data = pd.read_parquet(
            str(Path(self.lakehouse.root_path) / "credit_features_incremental")
        )

        logger.info(f"Ingested from production: {len(transactions)} transactions, {len(credit_data)} credit records")

        return {
            "transactions": transactions,
            "credit_data": credit_data,
            "graph_data": self._build_graph_from_transactions(transactions),
            "source": "production",
            "timestamp": datetime.now().isoformat(),
        }

    def _ingest_from_file(self, data_path: str) -> Dict[str, Any]:
        """Ingest from a Parquet or CSV file"""
        if not data_path:
            raise ValueError("--data-path required for file mode")

        path = Path(data_path)
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        logger.info(f"Ingested from file: {len(df)} records")

        # Store in lakehouse for versioning
        version_tag = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.lakehouse.write_training_data(df, "fraud_transactions_incremental", version_tag=version_tag)

        return {
            "transactions": df,
            "credit_data": df if "credit_score" in df.columns else pd.DataFrame(),
            "graph_data": self._build_graph_from_transactions(df),
            "source": f"file:{path.name}",
            "timestamp": datetime.now().isoformat(),
        }

    def _ingest_synthetic(self, n_transactions: int, n_customers: int, n_agents: int, seed: int = None) -> Dict[str, Any]:
        """Generate new synthetic data for continue training"""
        actual_seed = seed or int(time.time()) % 100000
        data = generate_training_dataset(
            n_transactions=n_transactions,
            n_customers=n_customers,
            n_agents=n_agents,
            seed=actual_seed,
        )

        # Store in lakehouse
        version_tag = f"synthetic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.lakehouse.write_training_data(
            data["transactions"], "fraud_transactions", version_tag=version_tag, mode="append"
        )
        self.lakehouse.write_training_data(
            data["credit_data"], "credit_features", version_tag=version_tag, mode="append"
        )

        logger.info(f"Generated synthetic: {len(data['transactions'])} transactions (seed={actual_seed})")

        return {
            "transactions": data["transactions"],
            "credit_data": data["credit_data"],
            "graph_data": data["graph_data"],
            "source": f"synthetic(seed={actual_seed})",
            "timestamp": datetime.now().isoformat(),
        }

    def _build_graph_from_transactions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Build transaction graph from DataFrame for GNN training"""
        if "customer_id" not in df.columns or "agent_id" not in df.columns:
            return None

        customers = df["customer_id"].unique()
        agents = df["agent_id"].unique()
        n_customers = len(customers)
        n_agents = len(agents)

        cust_map = {c: i for i, c in enumerate(customers)}
        agent_map = {a: i + n_customers for i, a in enumerate(agents)}

        edges_src = []
        edges_dst = []
        for _, row in df.iterrows():
            if row["customer_id"] in cust_map and row["agent_id"] in agent_map:
                edges_src.append(cust_map[row["customer_id"]])
                edges_dst.append(agent_map[row["agent_id"]])

        edge_index = np.array([edges_src + edges_dst, edges_dst + edges_src])
        n_nodes = n_customers + n_agents
        node_features = np.random.randn(n_nodes, 16).astype(np.float32)
        node_labels = np.zeros(n_nodes, dtype=np.int64)

        # Label fraud-associated nodes
        fraud_customers = set(df[df.get("is_fraud", pd.Series([0]*len(df))) == 1]["customer_id"].unique())
        for c, idx in cust_map.items():
            if c in fraud_customers:
                node_labels[idx] = 1

        return {
            "node_features": node_features,
            "edge_index": edge_index,
            "node_labels": node_labels,
            "n_customers": n_customers,
            "n_agents": n_agents,
        }

    def continue_train_fraud_models(
        self,
        new_data: pd.DataFrame,
        existing_weights: Dict[str, Any],
    ) -> Dict[str, Dict]:
        """Continue training fraud detection models from existing weights"""
        logger.info("=" * 50)
        logger.info("CONTINUE TRAINING: Fraud Detection Models")
        logger.info("=" * 50)

        results = {}

        # Load existing feature engineer
        fe = FraudFeatureEngineer()
        fe_state = existing_weights.get("fraud_feature_engineer")
        if fe_state:
            fe.scaler = fe_state["scaler"]
            fe.encoders = fe_state["encoders"]
            fe.feature_names = fe_state["feature_names"]
            fe.is_fitted = True
            X = fe.transform(new_data)
        else:
            X = fe.fit_transform(new_data)

        y = new_data["is_fraud"].values.astype(np.float32)

        # Split: use 80/20 for continue training (smaller validation)
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        fraud_rate = y.mean()
        logger.info(f"New data: {len(X)} samples, fraud_rate={fraud_rate:.4f}")

        # 1. XGBoost — warm start (continue boosting from existing model)
        if "fraud_xgboost" in existing_weights:
            results["xgboost"] = self._continue_xgboost(
                existing_weights["fraud_xgboost"]["model"],
                X_train, y_train, X_val, y_val,
                model_name="fraud_xgboost"
            )

        # 2. LightGBM — warm start
        if "fraud_lightgbm" in existing_weights:
            results["lightgbm"] = self._continue_lightgbm(
                existing_weights["fraud_lightgbm"]["model"],
                X_train, y_train, X_val, y_val,
                model_name="fraud_lightgbm"
            )

        # 3. RandomForest — warm start (add more trees)
        if "fraud_random_forest" in existing_weights:
            results["random_forest"] = self._continue_random_forest(
                existing_weights["fraud_random_forest"]["model"],
                X_train, y_train, X_val, y_val,
                model_name="fraud_random_forest"
            )

        # 4. DNN — fine-tune with lower learning rate
        if "fraud_dnn_best" in existing_weights:
            results["dnn"] = self._continue_dnn(
                existing_weights["fraud_dnn_best"]["checkpoint"],
                X_train, y_train, X_val, y_val,
                model_name="fraud_dnn"
            )

        # 5. IsolationForest — refit (no warm_start support)
        if "fraud_isolation_forest" in existing_weights:
            results["isolation_forest"] = self._continue_isolation_forest(
                X_train, y_train, X_val, y_val,
                fraud_rate=fraud_rate,
                model_name="fraud_isolation_forest"
            )

        # Save updated feature engineer
        fe.save(self.models_dir / "fraud_feature_engineer.joblib")

        return results

    def _continue_xgboost(
        self, existing_model, X_train, y_train, X_val, y_val, model_name: str
    ) -> Dict:
        """Continue XGBoost training from existing model (incremental boosting)"""
        import xgboost as xgb

        logger.info(f"  Continue training {model_name} (XGBoost warm_start)")
        logger.info(f"    Existing n_estimators: {existing_model.n_estimators}")

        # XGBoost supports continuing training via xgb_model parameter
        # Add 100 more boosting rounds on new data
        new_model = xgb.XGBClassifier(
            n_estimators=100,  # Additional rounds
            max_depth=existing_model.max_depth,
            learning_rate=existing_model.learning_rate * self.lr_multiplier,  # Lower LR for fine-tuning
            scale_pos_weight=float(np.sum(y_train == 0)) / max(np.sum(y_train == 1), 1),
            eval_metric="auc",
            early_stopping_rounds=20,
            random_state=42,
            use_label_encoder=False,
            tree_method="hist",
        )

        # Continue from existing model
        new_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            xgb_model=existing_model.get_booster(),
            verbose=False,
        )

        # Evaluate
        from sklearn.metrics import roc_auc_score, f1_score
        y_pred_proba = new_model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba)
        f1 = f1_score(y_val, y_pred)

        logger.info(f"    After continue training: AUC={auc:.4f}, F1={f1:.4f}")
        logger.info(f"    Total estimators: {new_model.n_estimators + existing_model.n_estimators}")

        # Save
        joblib.dump(new_model, self.models_dir / f"{model_name}.joblib")

        return {"auc": auc, "f1": f1, "n_estimators_added": 100, "method": "xgb_model_warm_start"}

    def _continue_lightgbm(
        self, existing_model, X_train, y_train, X_val, y_val, model_name: str
    ) -> Dict:
        """Continue LightGBM training with init_model (incremental boosting)"""
        import lightgbm as lgb_module

        logger.info(f"  Continue training {model_name} (LightGBM init_model)")

        # Save existing model to temp file for init_model
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            existing_model.booster_.save_model(tmp.name)
            init_model_path = tmp.name

        new_model = lgb_module.LGBMClassifier(
            n_estimators=100,  # Additional rounds
            max_depth=existing_model.max_depth,
            learning_rate=existing_model.learning_rate * self.lr_multiplier,
            is_unbalance=True,
            random_state=42,
            verbose=-1,
        )

        # Continue from existing model via init_model
        new_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            eval_metric="auc",
            callbacks=[lgb_module.early_stopping(20, verbose=False)],
            init_model=init_model_path,
        )

        # Evaluate
        from sklearn.metrics import roc_auc_score, f1_score
        y_pred_proba = new_model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba)
        f1 = f1_score(y_val, y_pred)

        logger.info(f"    After continue training: AUC={auc:.4f}, F1={f1:.4f}")

        # Save
        joblib.dump(new_model, self.models_dir / f"{model_name}.joblib")

        # Cleanup
        Path(init_model_path).unlink(missing_ok=True)

        return {"auc": auc, "f1": f1, "n_estimators_added": 100, "method": "lgb_init_model"}

    def _continue_random_forest(
        self, existing_model, X_train, y_train, X_val, y_val, model_name: str
    ) -> Dict:
        """Continue RandomForest with warm_start (add more trees)"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import roc_auc_score, f1_score

        logger.info(f"  Continue training {model_name} (RF warm_start)")
        logger.info(f"    Existing n_estimators: {existing_model.n_estimators}")

        # Enable warm_start and add 50 more trees
        existing_model.warm_start = True
        existing_model.n_estimators += 50
        existing_model.fit(X_train, y_train)

        # Evaluate
        y_pred_proba = existing_model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba)
        f1 = f1_score(y_val, y_pred)

        logger.info(f"    After continue training: AUC={auc:.4f}, F1={f1:.4f}")
        logger.info(f"    Total estimators: {existing_model.n_estimators}")

        # Save
        joblib.dump(existing_model, self.models_dir / f"{model_name}.joblib")

        return {"auc": auc, "f1": f1, "n_estimators_total": existing_model.n_estimators, "method": "warm_start"}

    def _continue_dnn(
        self, checkpoint: Dict, X_train, y_train, X_val, y_val, model_name: str
    ) -> Dict:
        """Fine-tune PyTorch DNN with lower learning rate from checkpoint"""
        from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
        from sklearn.metrics import roc_auc_score, f1_score

        logger.info(f"  Fine-tuning {model_name} (PyTorch, LR×{self.lr_multiplier})")

        # Reconstruct model from checkpoint
        input_dim = checkpoint["input_dim"]
        hidden_dims = checkpoint.get("hidden_dims", [256, 128, 64])
        dropout = checkpoint.get("dropout", 0.3)

        model = FraudDetectionDNN(input_dim=input_dim, hidden_dims=hidden_dims, dropout=dropout)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(self.device)

        # Lower learning rate for fine-tuning
        base_lr = 0.001
        fine_tune_lr = base_lr * self.lr_multiplier
        optimizer = torch.optim.AdamW(model.parameters(), lr=fine_tune_lr, weight_decay=1e-4)

        # Optionally load optimizer state for smoother continuation
        if "optimizer_state_dict" in checkpoint:
            try:
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                # Override LR with fine-tune LR
                for param_group in optimizer.param_groups:
                    param_group["lr"] = fine_tune_lr
            except (ValueError, KeyError):
                pass  # Architecture mismatch, use fresh optimizer

        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30)
        criterion = torch.nn.BCELoss()

        # Weighted sampling
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        sample_weights = np.where(y_train == 1, n_neg / max(n_pos, 1), 1.0)
        sampler = WeightedRandomSampler(
            weights=torch.DoubleTensor(sample_weights),
            num_samples=len(sample_weights),
            replacement=True
        )

        train_dataset = TensorDataset(
            torch.FloatTensor(X_train).to(self.device),
            torch.FloatTensor(y_train).to(self.device)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val).to(self.device),
            torch.FloatTensor(y_val).to(self.device)
        )

        train_loader = DataLoader(train_dataset, batch_size=512, sampler=sampler)
        val_loader = DataLoader(val_dataset, batch_size=1024)

        # Fine-tuning loop (fewer epochs, early stopping)
        best_val_auc = checkpoint.get("val_auc", 0)
        patience = 10
        patience_counter = 0
        fine_tune_epochs = 50

        logger.info(f"    Starting from epoch {checkpoint.get('epoch', 0)+1}, best AUC={best_val_auc:.4f}")

        for epoch in range(fine_tune_epochs):
            model.train()
            train_loss = 0
            n_batches = 0

            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1

            scheduler.step()

            # Validation
            model.eval()
            val_preds = []
            val_labels = []
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    outputs = model(batch_X)
                    val_preds.extend(outputs.cpu().numpy())
                    val_labels.extend(batch_y.cpu().numpy())

            val_auc = roc_auc_score(val_labels, val_preds)

            if (epoch + 1) % 10 == 0:
                logger.info(f"    Fine-tune epoch {epoch+1}/{fine_tune_epochs} - "
                            f"Loss: {train_loss/max(n_batches,1):.4f}, Val AUC: {val_auc:.4f}")

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                patience_counter = 0
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "epoch": checkpoint.get("epoch", 0) + epoch + 1,
                    "val_auc": val_auc,
                    "input_dim": input_dim,
                    "hidden_dims": hidden_dims,
                    "dropout": dropout,
                    "fine_tuned": True,
                    "fine_tune_lr": fine_tune_lr,
                    "continue_from_epoch": checkpoint.get("epoch", 0),
                }, self.models_dir / f"{model_name}_best.pt")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"    Early stopping at fine-tune epoch {epoch+1}")
                    break

        # Final evaluation
        best_ckpt = torch.load(self.models_dir / f"{model_name}_best.pt", map_location=self.device)
        model.load_state_dict(best_ckpt["model_state_dict"])
        model.eval()
        with torch.no_grad():
            X_val_t = torch.FloatTensor(X_val).to(self.device)
            y_pred_proba = model(X_val_t).cpu().numpy()
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba)
        f1 = f1_score(y_val, y_pred)

        logger.info(f"    Final fine-tuned: AUC={auc:.4f}, F1={f1:.4f}")

        return {
            "auc": auc, "f1": f1,
            "fine_tune_epochs": epoch + 1,
            "fine_tune_lr": fine_tune_lr,
            "method": "pytorch_fine_tune",
        }

    def _continue_isolation_forest(
        self, X_train, y_train, X_val, y_val, fraud_rate: float, model_name: str
    ) -> Dict:
        """Retrain IsolationForest (no warm_start — full refit on combined data)"""
        from sklearn.ensemble import IsolationForest
        from sklearn.metrics import roc_auc_score, f1_score

        logger.info(f"  Retraining {model_name} (full refit — no warm_start for IF)")

        model = IsolationForest(
            n_estimators=200,
            contamination=min(fraud_rate * 1.5, 0.1),
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train)

        # Evaluate
        scores = model.decision_function(X_val)
        y_pred_proba = 1 - (scores - scores.min()) / (scores.max() - scores.min())
        y_pred = (model.predict(X_val) == -1).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba)
        f1 = f1_score(y_val, y_pred)

        logger.info(f"    After retrain: AUC={auc:.4f}, F1={f1:.4f}")

        joblib.dump(model, self.models_dir / f"{model_name}.joblib")

        return {"auc": auc, "f1": f1, "method": "full_refit"}

    def continue_train_gnn_models(
        self,
        graph_data: Dict[str, Any],
        existing_weights: Dict[str, Any],
    ) -> Dict[str, Dict]:
        """Fine-tune GNN models from existing checkpoints"""
        if graph_data is None:
            logger.info("No graph data available — skipping GNN continue training")
            return {}

        logger.info("=" * 50)
        logger.info("CONTINUE TRAINING: GNN Models")
        logger.info("=" * 50)

        results = {}
        gnn_models = {
            "fraud_gcn_best": FraudGCN,
            "fraud_gat_best": FraudGAT,
            "fraud_graphsage_best": FraudGraphSAGE,
        }

        for model_name, ModelClass in gnn_models.items():
            if model_name not in existing_weights:
                continue

            checkpoint = existing_weights[model_name]["checkpoint"]
            in_channels = checkpoint["in_channels"]

            # Reconstruct and load
            model = ModelClass(in_channels=in_channels)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.to(self.device)

            # Fine-tune with lower LR
            fine_tune_lr = 0.01 * self.lr_multiplier
            optimizer = torch.optim.Adam(model.parameters(), lr=fine_tune_lr, weight_decay=5e-4)

            # Prepare graph data
            node_features = torch.FloatTensor(graph_data["node_features"][:, :in_channels]).to(self.device)
            edge_index = torch.LongTensor(graph_data["edge_index"]).to(self.device)
            labels = torch.LongTensor(graph_data["node_labels"]).to(self.device)

            # Train mask (80% train, 20% val)
            n_nodes = len(graph_data["node_labels"])
            perm = np.random.permutation(n_nodes)
            train_mask = torch.zeros(n_nodes, dtype=torch.bool)
            train_mask[perm[:int(0.8 * n_nodes)]] = True
            val_mask = ~train_mask

            # Fine-tuning loop
            best_val_auc = checkpoint.get("val_auc", 0)
            patience = 20
            patience_counter = 0

            for epoch in range(100):
                model.train()
                optimizer.zero_grad()
                out = model(node_features, edge_index)
                loss = torch.nn.functional.cross_entropy(out[train_mask], labels[train_mask])
                loss.backward()
                optimizer.step()

                # Validation
                model.eval()
                with torch.no_grad():
                    out = model(node_features, edge_index)
                    val_probs = torch.softmax(out[val_mask], dim=1)[:, 1].cpu().numpy()
                    val_labels = labels[val_mask].cpu().numpy()

                try:
                    from sklearn.metrics import roc_auc_score
                    val_auc = roc_auc_score(val_labels, val_probs)
                except ValueError:
                    val_auc = 0.5

                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    patience_counter = 0
                    torch.save({
                        "model_state_dict": model.state_dict(),
                        "epoch": checkpoint.get("epoch", 0) + epoch + 1,
                        "val_auc": val_auc,
                        "model_class": ModelClass.__name__,
                        "in_channels": in_channels,
                        "fine_tuned": True,
                    }, self.models_dir / f"{model_name}.pt")
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        break

            short_name = model_name.replace("fraud_", "").replace("_best", "")
            results[short_name] = {
                "auc": best_val_auc,
                "fine_tune_epochs": epoch + 1,
                "method": "pytorch_gnn_fine_tune",
            }
            logger.info(f"  {model_name}: AUC={best_val_auc:.4f} after {epoch+1} fine-tune epochs")

        return results

    def continue_train_credit_models(
        self,
        credit_data: pd.DataFrame,
        existing_weights: Dict[str, Any],
    ) -> Dict[str, Dict]:
        """Continue training credit scoring models"""
        if credit_data is None or len(credit_data) == 0:
            logger.info("No credit data — skipping credit continue training")
            return {}

        logger.info("=" * 50)
        logger.info("CONTINUE TRAINING: Credit Scoring Models")
        logger.info("=" * 50)

        results = {}

        # Load credit feature engineer
        fe_state = existing_weights.get("credit_feature_engineer")
        credit_trainer = CreditScoringTrainer(output_dir=self.models_dir)

        # For credit models, use the full trainer with new data
        # The trainer handles feature engineering internally
        credit_results = credit_trainer.train_all(credit_data)

        for model_name, metrics in credit_results.items():
            results[model_name] = metrics
            results[model_name]["method"] = "full_retrain_on_new_data"

        return results

    def evaluate_improvement(
        self,
        old_metrics: Dict[str, Dict],
        new_metrics: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """Compare new model metrics against old and determine if improvement is significant"""
        improvements = {}

        for model_name, new_m in new_metrics.items():
            old_m = old_metrics.get(model_name, {})
            if not old_m:
                improvements[model_name] = {
                    "improved": True,
                    "reason": "No previous metrics (new model)",
                    "new_auc": new_m.get("auc"),
                }
                continue

            old_auc = old_m.get("auc", 0)
            new_auc = new_m.get("auc", 0)
            delta = new_auc - old_auc

            improved = delta >= self.improvement_threshold
            improvements[model_name] = {
                "improved": improved,
                "old_auc": old_auc,
                "new_auc": new_auc,
                "delta": delta,
                "threshold": self.improvement_threshold,
                "reason": f"AUC improved by {delta:.4f}" if improved else f"AUC change {delta:.4f} below threshold {self.improvement_threshold}",
            }

        return improvements

    def register_improved_models(
        self,
        improvements: Dict[str, Any],
        data_source: str,
    ) -> List[str]:
        """Register improved models as new versions in the registry"""
        registered = []

        for model_name, improvement in improvements.items():
            if not improvement["improved"]:
                continue

            # Find artifact
            artifact_name = f"fraud_{model_name}" if not model_name.startswith(("fraud_", "credit_")) else model_name
            for ext in [".joblib", "_best.pt"]:
                artifact_path = self.models_dir / f"{artifact_name}{ext}"
                if artifact_path.exists():
                    # Determine model type
                    if "credit" in model_name:
                        model_type = ModelType.CREDIT_SCORING
                    elif "gnn" in model_name or "gcn" in model_name or "gat" in model_name or "sage" in model_name:
                        model_type = ModelType.GNN_FRAUD
                    else:
                        model_type = ModelType.FRAUD_DETECTION

                    meta = self.registry.register_model(
                        model_name=artifact_name,
                        model_type=model_type,
                        artifact_path=str(artifact_path),
                        metrics={"auc": improvement["new_auc"], "delta": improvement["delta"]},
                        description=f"Continue training from {data_source}",
                        tags={"method": "continue_training", "data_source": data_source},
                    )
                    registered.append(artifact_name)
                    logger.info(f"  Registered {artifact_name} v{meta['version']} (AUC={improvement['new_auc']:.4f})")
                    break

        return registered

    def setup_ab_test(
        self,
        registered_models: List[str],
    ) -> Optional[str]:
        """Set up A/B test between old and new model versions"""
        if not registered_models:
            return None

        ab_manager = ABTestManager(storage_path=str(self.models_dir.parent / "ab_tests"))

        # Create experiment for first improved model
        model_name = registered_models[0]
        exp = ab_manager.create_experiment(
            name=f"continue_training_{model_name}_{datetime.now().strftime('%Y%m%d')}",
            variants=[
                {"name": "champion", "model_name": model_name, "model_version": 1, "traffic_weight": 0.8},
                {"name": "challenger", "model_name": model_name, "model_version": 2, "traffic_weight": 0.2},
            ],
            metric_name="auc",
            allocation_strategy="canary",
            description=f"A/B test: existing vs continue-trained {model_name}",
        )
        ab_manager.start_experiment(exp.experiment_id)
        logger.info(f"  A/B test started: {exp.experiment_id} (80/20 canary)")

        return exp.experiment_id

    def _get_last_ingestion_timestamp(self, table_name: str) -> Optional[str]:
        """Get last ingestion timestamp for incremental loading"""
        meta_path = Path(self.lakehouse.root_path) / "_metadata"
        if not meta_path.exists():
            return None

        meta_files = sorted(meta_path.glob(f"{table_name}_*.json"), reverse=True)
        if meta_files:
            import json
            with open(meta_files[0]) as f:
                meta = json.load(f)
            return meta.get("timestamp")
        return None

    def run(
        self,
        mode: str,
        models: List[str] = None,
        db_url: str = None,
        data_path: str = None,
        n_transactions: int = 50000,
        seed: int = None,
        skip_ab_test: bool = False,
    ) -> Dict[str, Any]:
        """Execute full continue training pipeline"""
        start_time = time.time()
        models = models or ["fraud", "gnn", "credit"]

        logger.info("=" * 70)
        logger.info("54agent ML PIPELINE — CONTINUE TRAINING")
        logger.info("=" * 70)
        logger.info(f"Mode: {mode}, Models: {models}, LR multiplier: {self.lr_multiplier}")

        # Step 1: Load existing weights
        logger.info("\n[Step 1] Loading existing model weights...")
        existing_weights = self.load_existing_weights()
        logger.info(f"  Loaded {len(existing_weights)} model artifacts")

        # Step 2: Get old metrics from registry
        logger.info("\n[Step 2] Loading baseline metrics from registry...")
        old_models = self.registry.list_models()
        self.old_metrics = {}
        for m in old_models:
            self.old_metrics[m["model_name"]] = m.get("metrics", {})

        # Step 3: Ingest new data
        logger.info("\n[Step 3] Ingesting new training data...")
        new_data = self.ingest_new_data(
            mode=mode, db_url=db_url, data_path=data_path,
            n_transactions=n_transactions, seed=seed,
        )

        # Step 4: Continue training
        all_results = {}

        if "fraud" in models and new_data.get("transactions") is not None:
            fraud_results = self.continue_train_fraud_models(
                new_data["transactions"], existing_weights
            )
            all_results.update({f"fraud_{k}": v for k, v in fraud_results.items()})

        if "gnn" in models and new_data.get("graph_data") is not None:
            gnn_results = self.continue_train_gnn_models(
                new_data["graph_data"], existing_weights
            )
            all_results.update({f"gnn_{k}": v for k, v in gnn_results.items()})

        if "credit" in models and new_data.get("credit_data") is not None:
            credit_results = self.continue_train_credit_models(
                new_data["credit_data"], existing_weights
            )
            all_results.update({f"credit_{k}": v for k, v in credit_results.items()})

        # Step 5: Evaluate improvements
        logger.info("\n[Step 5] Evaluating improvements...")
        improvements = self.evaluate_improvement(self.old_metrics, all_results)
        improved = [k for k, v in improvements.items() if v.get("improved")]
        logger.info(f"  Improved models: {len(improved)}/{len(all_results)}")
        for name, imp in improvements.items():
            status = "✓" if imp["improved"] else "✗"
            logger.info(f"    {status} {name}: {imp['reason']}")

        # Step 6: Register improved models
        logger.info("\n[Step 6] Registering improved models...")
        registered = self.register_improved_models(improvements, data_source=new_data.get("source", mode))
        logger.info(f"  Registered {len(registered)} new model versions")

        # Step 7: A/B test
        ab_experiment_id = None
        if not skip_ab_test and registered:
            logger.info("\n[Step 7] Setting up A/B test...")
            ab_experiment_id = self.setup_ab_test(registered)

        # Summary
        total_time = time.time() - start_time
        summary = {
            "training_mode": "continue",
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": total_time,
            "data_source": new_data.get("source", mode),
            "lr_multiplier": self.lr_multiplier,
            "models_trained": len(all_results),
            "models_improved": len(improved),
            "models_registered": registered,
            "ab_experiment_id": ab_experiment_id,
            "results": all_results,
            "improvements": improvements,
        }

        # Save summary
        summary_path = self.models_dir / "continue_training_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info("\n" + "=" * 70)
        logger.info("CONTINUE TRAINING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Duration: {total_time:.1f}s")
        logger.info(f"Improved: {len(improved)}/{len(all_results)} models")
        logger.info(f"Registered: {len(registered)} new versions")
        if ab_experiment_id:
            logger.info(f"A/B test: {ab_experiment_id}")

        return summary


def main():
    parser = argparse.ArgumentParser(description="Continue training ML models on new data")
    parser.add_argument("--mode", choices=["synthetic", "production", "file"], default="synthetic",
                       help="Data source mode")
    parser.add_argument("--db-url", type=str, help="PostgreSQL connection URL (for production mode)")
    parser.add_argument("--data-path", type=str, help="Path to data file (for file mode)")
    parser.add_argument("--n-transactions", type=int, default=50000,
                       help="Number of new transactions (synthetic mode)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (None=time-based)")
    parser.add_argument("--models", nargs="+", default=["fraud", "gnn", "credit"],
                       choices=["fraud", "gnn", "credit"],
                       help="Which model types to retrain")
    parser.add_argument("--lr-multiplier", type=float, default=0.1,
                       help="Learning rate multiplier for fine-tuning (0.1 = 10%% of original LR)")
    parser.add_argument("--improvement-threshold", type=float, default=0.005,
                       help="Minimum AUC improvement to register new version")
    parser.add_argument("--skip-ab-test", action="store_true",
                       help="Skip A/B test setup")
    parser.add_argument("--output-dir", type=str, default=str(MODELS_DIR),
                       help="Model weights directory")

    args = parser.parse_args()

    trainer = ContinualTrainer(
        models_dir=Path(args.output_dir),
        lr_multiplier=args.lr_multiplier,
        improvement_threshold=args.improvement_threshold,
    )

    summary = trainer.run(
        mode=args.mode,
        models=args.models,
        db_url=args.db_url,
        data_path=args.data_path,
        n_transactions=args.n_transactions,
        seed=args.seed,
        skip_ab_test=args.skip_ab_test,
    )

    return summary


if __name__ == "__main__":
    main()
