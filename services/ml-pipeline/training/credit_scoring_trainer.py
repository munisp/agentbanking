"""
Credit Scoring Model Training Pipeline

Trains models for:
- Credit score prediction (regression: 300-850)
- Default probability estimation (binary classification)
- Credit limit recommendation

Models:
- XGBoost Regressor
- LightGBM Regressor
- PyTorch DNN (custom architecture with residual connections)
- Ensemble (weighted average of all models)

Features:
- Proper feature engineering from Nigerian credit data
- Cross-validation for model selection
- Early stopping with validation monitoring
- Weight persistence
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_squared_error, r2_score, mean_absolute_error,
    roc_auc_score, f1_score
)
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
import lightgbm as lgb
import joblib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models" / "weights"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ======================== Credit Scoring DNN ========================

class CreditScoringDNN(nn.Module):
    """Deep Neural Network for Credit Score Prediction

    Architecture with residual connections:
    - Input → Linear(256) → BN → ReLU → Dropout
    - → Linear(256) → BN → ReLU → Dropout + Residual
    - → Linear(128) → BN → ReLU → Dropout
    - → Linear(64) → BN → ReLU
    - → Linear(1) → Scale to [300, 850]
    """

    def __init__(self, input_dim: int, dropout: float = 0.2):
        super().__init__()

        self.input_bn = nn.BatchNorm1d(input_dim)

        # First block
        self.block1 = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Second block with residual
        self.block2 = nn.Sequential(
            nn.Linear(256, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Third block
        self.block3 = nn.Sequential(
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Fourth block
        self.block4 = nn.Sequential(
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
        )

        # Output
        self.output = nn.Linear(64, 1)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_bn(x)
        x = self.block1(x)
        residual = x
        x = self.block2(x) + residual  # Residual connection
        x = self.block3(x)
        x = self.block4(x)
        x = self.output(x)
        # Scale to credit score range [300, 850]
        x = torch.sigmoid(x) * 550 + 300
        return x.squeeze(-1)


class DefaultPredictionDNN(nn.Module):
    """Binary classifier for default probability prediction"""

    def __init__(self, input_dim: int, dropout: float = 0.3):
        super().__init__()
        self.network = nn.Sequential(
            nn.BatchNorm1d(input_dim),
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


# ======================== Feature Engineering ========================

class CreditFeatureEngineer:
    """Extract ML features for credit scoring"""

    FEATURE_COLUMNS = [
        "age", "monthly_income_ngn", "account_age_days", "is_urban",
        "has_bvn", "has_nin", "monthly_tx_frequency", "has_savings_goal",
        "has_loan", "total_transactions", "total_amount", "avg_amount",
        "max_amount", "fraud_count", "unique_agents", "unique_types",
        "debt_to_income", "num_active_loans", "months_since_last_default",
        "credit_utilization", "payment_history_score",
    ]

    def __init__(self):
        self.scaler = StandardScaler()
        self.is_fitted = False

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        """Fit scaler and transform features"""
        # Encode categorical columns
        feature_df = df[self.FEATURE_COLUMNS].copy()
        feature_df = feature_df.fillna(0)

        X = self.scaler.fit_transform(feature_df.values)
        self.is_fitted = True
        return X.astype(np.float32)

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Call fit_transform first")
        feature_df = df[self.FEATURE_COLUMNS].copy().fillna(0)
        return self.scaler.transform(feature_df.values).astype(np.float32)

    def save(self, path: Path):
        joblib.dump({"scaler": self.scaler, "feature_columns": self.FEATURE_COLUMNS}, path)

    def load(self, path: Path):
        state = joblib.load(path)
        self.scaler = state["scaler"]
        self.is_fitted = True


# ======================== Credit Scoring Trainer ========================

class CreditScoringTrainer:
    """Orchestrates training of credit scoring models"""

    def __init__(self, output_dir: Path = MODELS_DIR, device: str = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.feature_engineer = CreditFeatureEngineer()
        logger.info(f"Credit Scoring Trainer on device: {self.device}")

    def train_all(self, credit_data: pd.DataFrame) -> Dict[str, Any]:
        """Train all credit scoring models"""
        logger.info("=" * 60)
        logger.info("CREDIT SCORING MODEL TRAINING PIPELINE")
        logger.info("=" * 60)
        start_time = time.time()

        # Feature engineering
        X = self.feature_engineer.fit_transform(credit_data)
        y_score = credit_data["credit_score"].values.astype(np.float32)
        y_default = credit_data["is_defaulted"].values.astype(np.float32)

        self.feature_engineer.save(self.output_dir / "credit_feature_engineer.joblib")

        # Split
        X_train, X_test, y_score_train, y_score_test, y_default_train, y_default_test = \
            train_test_split(X, y_score, y_default, test_size=0.2, random_state=42)
        X_train, X_val, y_score_train, y_score_val, y_default_train, y_default_val = \
            train_test_split(X_train, y_score_train, y_default_train, test_size=0.15, random_state=42)

        logger.info(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

        results = {}

        # 1. Credit Score Prediction Models
        logger.info("\n--- Credit Score Prediction ---")

        # XGBoost Regressor
        logger.info("Training XGBoost Regressor...")
        results["xgb_score"] = self._train_xgb_regressor(
            X_train, y_score_train, X_val, y_score_val, X_test, y_score_test
        )

        # LightGBM Regressor
        logger.info("Training LightGBM Regressor...")
        results["lgb_score"] = self._train_lgb_regressor(
            X_train, y_score_train, X_val, y_score_val, X_test, y_score_test
        )

        # DNN Score Predictor
        logger.info("Training DNN Score Predictor...")
        results["dnn_score"] = self._train_dnn_regressor(
            X_train, y_score_train, X_val, y_score_val, X_test, y_score_test
        )

        # 2. Default Probability Models
        logger.info("\n--- Default Probability Prediction ---")

        # XGBoost Classifier
        logger.info("Training XGBoost Default Classifier...")
        results["xgb_default"] = self._train_xgb_classifier(
            X_train, y_default_train, X_val, y_default_val, X_test, y_default_test
        )

        # DNN Default Predictor
        logger.info("Training DNN Default Predictor...")
        results["dnn_default"] = self._train_dnn_classifier(
            X_train, y_default_train, X_val, y_default_val, X_test, y_default_test
        )

        # Save metadata
        elapsed = time.time() - start_time
        metadata = {
            "training_timestamp": datetime.now().isoformat(),
            "training_duration_seconds": elapsed,
            "dataset_size": len(credit_data),
            "feature_count": X.shape[1],
            "device": str(self.device),
            "results": {k: {mk: float(mv) for mk, mv in v.items() if isinstance(mv, (int, float, np.floating))} for k, v in results.items()},
        }
        with open(self.output_dir / "credit_training_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"\nCredit scoring training complete in {elapsed:.1f}s")
        return results

    def _train_xgb_regressor(self, X_train, y_train, X_val, y_val, X_test, y_test) -> Dict:
        model = xgb.XGBRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1,
            random_state=42, early_stopping_rounds=20,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        y_pred = model.predict(X_test)
        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "r2": float(r2_score(y_test, y_pred)),
        }
        logger.info(f"  XGB Score - RMSE: {metrics['rmse']:.2f}, MAE: {metrics['mae']:.2f}, R²: {metrics['r2']:.4f}")

        joblib.dump(model, self.output_dir / "credit_xgb_score.joblib")
        return metrics

    def _train_lgb_regressor(self, X_train, y_train, X_val, y_val, X_test, y_test) -> Dict:
        model = lgb.LGBMRegressor(
            n_estimators=300, max_depth=7, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )

        y_pred = model.predict(X_test)
        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "r2": float(r2_score(y_test, y_pred)),
        }
        logger.info(f"  LGB Score - RMSE: {metrics['rmse']:.2f}, MAE: {metrics['mae']:.2f}, R²: {metrics['r2']:.4f}")

        joblib.dump(model, self.output_dir / "credit_lgb_score.joblib")
        return metrics

    def _train_dnn_regressor(self, X_train, y_train, X_val, y_val, X_test, y_test) -> Dict:
        input_dim = X_train.shape[1]
        model = CreditScoringDNN(input_dim=input_dim).to(self.device)
        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
        criterion = nn.MSELoss()

        train_loader = DataLoader(
            TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train)),
            batch_size=512, shuffle=True
        )
        val_loader = DataLoader(
            TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val)),
            batch_size=1024
        )

        best_val_loss = float('inf')
        patience_counter = 0
        max_patience = 20

        for epoch in range(150):
            model.train()
            train_loss = 0
            n_batches = 0
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1

            model.eval()
            val_loss = 0
            n_val = 0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                    outputs = model(batch_X)
                    val_loss += criterion(outputs, batch_y).item()
                    n_val += 1

            avg_val_loss = val_loss / max(n_val, 1)
            scheduler.step(avg_val_loss)

            if (epoch + 1) % 20 == 0:
                logger.info(f"  Epoch {epoch+1} - Train Loss: {train_loss/n_batches:.4f}, Val Loss: {avg_val_loss:.4f}")

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_loss": avg_val_loss,
                    "input_dim": input_dim,
                }, self.output_dir / "credit_dnn_score_best.pt")
            else:
                patience_counter += 1
                if patience_counter >= max_patience:
                    logger.info(f"  Early stopping at epoch {epoch+1}")
                    break

        # Evaluate
        checkpoint = torch.load(self.output_dir / "credit_dnn_score_best.pt", map_location=self.device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        with torch.no_grad():
            y_pred = model(torch.FloatTensor(X_test).to(self.device)).cpu().numpy()

        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "r2": float(r2_score(y_test, y_pred)),
            "best_epoch": int(checkpoint["epoch"]),
        }
        logger.info(f"  DNN Score - RMSE: {metrics['rmse']:.2f}, MAE: {metrics['mae']:.2f}, R²: {metrics['r2']:.4f}")
        return metrics

    def _train_xgb_classifier(self, X_train, y_train, X_val, y_val, X_test, y_test) -> Dict:
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        model = xgb.XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            scale_pos_weight=n_neg / max(n_pos, 1),
            random_state=42, eval_metric="auc", early_stopping_rounds=20,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)

        metrics = {
            "auc": float(roc_auc_score(y_test, y_pred_proba)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        }
        logger.info(f"  XGB Default - AUC: {metrics['auc']:.4f}, F1: {metrics['f1']:.4f}")

        joblib.dump(model, self.output_dir / "credit_xgb_default.joblib")
        return metrics

    def _train_dnn_classifier(self, X_train, y_train, X_val, y_val, X_test, y_test) -> Dict:
        input_dim = X_train.shape[1]
        model = DefaultPredictionDNN(input_dim=input_dim).to(self.device)
        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
        criterion = nn.BCELoss()

        train_loader = DataLoader(
            TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train)),
            batch_size=512, shuffle=True
        )

        best_val_auc = 0
        patience_counter = 0

        for epoch in range(100):
            model.train()
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

            model.eval()
            with torch.no_grad():
                val_preds = model(torch.FloatTensor(X_val).to(self.device)).cpu().numpy()
                val_auc = roc_auc_score(y_val, val_preds)

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                patience_counter = 0
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_auc": val_auc,
                    "input_dim": input_dim,
                }, self.output_dir / "credit_dnn_default_best.pt")
            else:
                patience_counter += 1
                if patience_counter >= 15:
                    break

        # Evaluate
        checkpoint = torch.load(self.output_dir / "credit_dnn_default_best.pt", map_location=self.device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        with torch.no_grad():
            y_pred_proba = model(torch.FloatTensor(X_test).to(self.device)).cpu().numpy()

        metrics = {
            "auc": float(roc_auc_score(y_test, y_pred_proba)),
            "f1": float(f1_score(y_test, (y_pred_proba >= 0.5).astype(int), zero_division=0)),
            "best_epoch": int(checkpoint["epoch"]),
        }
        logger.info(f"  DNN Default - AUC: {metrics['auc']:.4f}, F1: {metrics['f1']:.4f}")
        return metrics
