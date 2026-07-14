import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV, StratifiedKFold
from sklearn.metrics import make_scorer, f1_score, roc_auc_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
import xgboost as xgb
import logging
import joblib
import mlflow
import mlflow.sklearn
from datetime import datetime

import time
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ModelTrainingService:
    """A comprehensive service for training, tuning, and tracking fraud detection models."""


    def __init__(self, experiment_name="FraudDetectionModels"):
        self.models = {
            'lightgbm': lgb.LGBMClassifier(random_state=42, objective='binary'),
            'xgboost': xgb.XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss')
        }
        self.best_model = None
        self.best_model_name = None
        self.experiment_name = experiment_name

        # Set up MLflow tracking
        try:
            mlflow.set_experiment(self.experiment_name)
            logging.info(f"MLflow experiment set to: {self.experiment_name}")
        except Exception as e:
            logging.error(f"Failed to set MLflow experiment: {e}")

    def _get_hyperparameter_grid(self, model_name):
        """Returns a hyperparameter grid for the specified model."""
        if model_name == 'lightgbm':
            return {
                'n_estimators': [100, 200, 500],
                'learning_rate': [0.01, 0.05, 0.1],
                'num_leaves': [31, 50, 100],
                'max_depth': [-1, 10, 20],
                'reg_alpha': [0.1, 0.5],
                'reg_lambda': [0.1, 0.5]
            }
        elif model_name == 'xgboost':
            return {
                'n_estimators': [100, 200, 500],
                'learning_rate': [0.01, 0.05, 0.1],
                'max_depth': [3, 5, 7],
                'subsample': [0.7, 0.8, 0.9],
                'colsample_bytree': [0.7, 0.8, 0.9]
            }
        else:
            raise ValueError("Unsupported model name.")

    def train_and_tune_model(self, features, labels, model_name='lightgbm', search_type='random', n_iter=50):
        """Trains and tunes a specified model using GridSearchCV or RandomizedSearchCV."""
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not supported.")

        X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42, stratify=labels)

        pipeline = Pipeline([('scaler', StandardScaler()), ('classifier', self.models[model_name])])
        param_grid = {f'classifier__{k}': v for k, v in self._get_hyperparameter_grid(model_name).items()}

        scoring = {
            'ROC_AUC': make_scorer(roc_auc_score, needs_proba=True),
            'F1': make_scorer(f1_score),
            'Precision': make_scorer(precision_score),
            'Recall': make_scorer(recall_score)
        }

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        if search_type == 'grid':
            search = GridSearchCV(pipeline, param_grid, cv=cv, scoring=scoring, refit='ROC_AUC', n_jobs=-1, verbose=1)
        elif search_type == 'random':
            search = RandomizedSearchCV(pipeline, param_grid, n_iter=n_iter, cv=cv, scoring=scoring, refit='ROC_AUC', n_jobs=-1, verbose=1, random_state=42)
        else:
            raise ValueError("search_type must be 'grid' or 'random'.")

        run_name = f"{model_name}_tuning_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with mlflow.start_run(run_name=run_name) as run:
            logging.info(f"Starting {search_type} search for {model_name}...")
            search.fit(X_train, y_train)

            self.best_model = search.best_estimator_
            self.best_model_name = model_name

            logging.info(f"Best parameters found: {search.best_params_}")
            logging.info(f"Best CV ROC AUC score: {search.best_score_:.4f}")

            y_pred = self.best_model.predict(X_test)
            y_proba = self.best_model.predict_proba(X_test)[:, 1]
            
            test_metrics = {
                'test_roc_auc': roc_auc_score(y_test, y_proba),
                'test_f1_score': f1_score(y_test, y_pred),
                'test_precision': precision_score(y_test, y_pred),
                'test_recall': recall_score(y_test, y_pred)
            }
            logging.info(f"Test Set Performance: {test_metrics}")

            mlflow.log_params(search.best_params_)
            mlflow.log_metrics({'best_cv_roc_auc': search.best_score_})
            mlflow.log_metrics(test_metrics)
            mlflow.sklearn.log_model(self.best_model, "model", registered_model_name=f"{model_name}-fraud-detector")

            run_id = run.info.run_id
            logging.info(f"MLflow Run ID: {run_id}")

        return self.best_model, run_id

    def retrain_with_new_data(self, model_uri, new_features, new_labels):
        """Retrains a previously logged model with new data."""

        logging.info(f"Retraining model from {model_uri} with {len(new_features)} new samples.")
        
        try:
            existing_model = mlflow.sklearn.load_model(model_uri)
        except Exception as e:
            logging.error(f"Failed to load model from {model_uri}: {e}")
            return None, None

        run_name = f"retraining_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with mlflow.start_run(run_name=run_name) as run:
            # For tree-based models, retraining often means training on a combined dataset.
            # A simpler approach (less ideal) is to just continue training if the model supports it.
            # XGBoost/LGBM can use `init_model` to continue training.
            # For this example, we'll just refit on the new data for demonstration.
            existing_model.fit(new_features, new_labels)
            
            mlflow.sklearn.log_model(existing_model, "retrained_model")
            logging.info("Model retraining complete and logged.")
            return existing_model, run.info.run_id

    def get_best_model_from_experiment(self, metric='metrics.test_roc_auc'):
        """Retrieves the best performing model from the MLflow experiment based on a metric."""

        logging.info(f"Searching for the best model in experiment '{self.experiment_name}' based on {metric}.")
        try:
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if not experiment:
                raise ValueError(f"Experiment '{self.experiment_name}' not found.")

            runs_df = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=[f'{metric} DESC'],
                max_results=1
            )
            if runs_df.empty:
                logging.warning("No runs found in the experiment.")
                return None, None

            best_run = runs_df.iloc[0]
            logging.info(f"Best run found: {best_run.run_id} with {metric}: {best_run[metric]:.4f}")
            model_uri = f"runs:/{best_run.run_id}/model"
            best_model = mlflow.sklearn.load_model(model_uri)
            return best_model, best_run.run_id
        except Exception as e:
            logging.error(f"Could not retrieve best model: {e}")
            return None, None

    def save_production_model(self, model, path):
        """Saves a model to a specified path for production deployment."""

        logging.info(f"Saving production-ready model to {path}")
        joblib.dump(model, path)

# Example Usage
if __name__ == '__main__':
    logging.info("--- Initializing Model Training Service ---")
    
    # Generate dummy data
    num_samples = 10000
    features = pd.DataFrame({f'feature_{i}': np.random.rand(num_samples) for i in range(30)})
    labels = pd.Series((np.random.rand(num_samples) < 0.05).astype(int)) # 5% fraud rate

    training_service = ModelTrainingService(experiment_name="Production_Fraud_Training")

    # 1. Train and tune LightGBM
    logging.info("--- Training and Tuning LightGBM ---")
    lgbm_model, lgbm_run_id = training_service.train_and_tune_model(
        features, labels, model_name='lightgbm', search_type='random', n_iter=15
    )

    # 2. Train and tune XGBoost
    logging.info("\n--- Training and Tuning XGBoost ---")
    xgb_model, xgb_run_id = training_service.train_and_tune_model(
        features, labels, model_name='xgboost', search_type='random', n_iter=15
    )

    # 3. Retrieve the best model from all runs
    logging.info("\n--- Retrieving Best Overall Model for Production ---")
    best_production_model, best_run_id = training_service.get_best_model_from_experiment()

    if best_production_model:
        # 4. Save the best model for deployment
        production_model_path = 'production_fraud_detector.joblib'
        training_service.save_production_model(best_production_model, production_model_path)

        # 5. Load and test the saved production model
        loaded_prod_model = joblib.load(production_model_path)
        sample_prediction = loaded_prod_model.predict(features.head(1))
        logging.info(f"\nPrediction with loaded production model: {'Fraud' if sample_prediction[0] == 1 else 'Not Fraud'}")
    else:
        logging.error("Could not retrieve a best model to save for production.")

    logging.info("\n--- Model Training and Management Pipeline Complete ---")

