import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
import logging
import joblib

import time
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EnsembleModelPlatform:
    """A robust platform for managing and deploying ensemble machine learning models for fraud detection."""


    def __init__(self, random_state=42):
        self.random_state = random_state
        self.base_models = {
            "random_forest": RandomForestClassifier(n_estimators=100, random_state=self.random_state, class_weight='balanced'),
            "gradient_boosting": GradientBoostingClassifier(n_estimators=100, random_state=self.random_state),
            "logistic_regression": LogisticRegression(random_state=self.random_state, solver='liblinear', class_weight='balanced'),
            "mlp_classifier": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=self.random_state),
            "decision_tree": DecisionTreeClassifier(random_state=self.random_state, class_weight='balanced')
        }
        self.trained_base_models = {}
        self.ensemble_model = None
        self.scaler = StandardScaler()
        self.feature_columns = None

    def _preprocess_data(self, features):
        logging.info("Preprocessing data for ensemble models...")
        # Ensure all features are numeric and handle NaNs
        features = features.select_dtypes(include=np.number).fillna(features.median())
        if self.feature_columns is None:
            self.feature_columns = features.columns
        else:
            # Ensure consistent columns during prediction
            missing_cols = set(self.feature_columns) - set(features.columns)
            for c in missing_cols:
                features[c] = 0
            features = features[self.feature_columns]

        scaled_features = self.scaler.fit_transform(features)
        return pd.DataFrame(scaled_features, columns=self.feature_columns)

    def train_base_models(self, features, labels):
        logging.info("Training individual base models...")
        preprocessed_features = self._preprocess_data(features)
        X_train, X_test, y_train, y_test = train_test_split(preprocessed_features, labels, test_size=0.2, random_state=self.random_state, stratify=labels)

        for name, model in self.base_models.items():
            logging.info(f"Training {name}...")
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1]
            
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred)
            recall = recall_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred)
            roc_auc = roc_auc_score(y_test, y_proba)

            logging.info(f"{name} - Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}, ROC AUC: {roc_auc:.4f}")
            self.trained_base_models[name] = model
        
        return X_test, y_test # Return test set for ensemble training

    def train_ensemble_model(self, X_test, y_test):
        logging.info("Training ensemble (VotingClassifier) model...")
        # Use the test set from base model training to train the ensemble
        estimators = [(name, model) for name, model in self.trained_base_models.items()]
        
        # Soft Voting for better performance with probability outputs
        self.ensemble_model = VotingClassifier(estimators=estimators, voting='soft', weights=[1, 1, 0.5, 1, 0.8]) # Assign weights based on performance/domain knowledge
        self.ensemble_model.fit(X_test, y_test)
        logging.info("Ensemble model trained successfully.")

    def evaluate_ensemble(self, features, labels):
        logging.info("Evaluating ensemble model...")
        if not self.ensemble_model:
            raise RuntimeError("Ensemble model not trained.")
        
        preprocessed_features = self._preprocess_data(features)
        y_pred = self.ensemble_model.predict(preprocessed_features)
        y_proba = self.ensemble_model.predict_proba(preprocessed_features)[:, 1]

        accuracy = accuracy_score(labels, y_pred)
        precision = precision_score(labels, y_pred)
        recall = recall_score(labels, y_pred)
        f1 = f1_score(labels, y_pred)
        roc_auc = roc_auc_score(labels, y_proba)

        logging.info(f"Ensemble - Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}, ROC AUC: {roc_auc:.4f}")
        return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1, "roc_auc": roc_auc}

    def predict_with_ensemble(self, new_data):
        logging.info("Making predictions with the ensemble model...")
        if not self.ensemble_model:
            raise RuntimeError("Ensemble model not trained.")
        
        preprocessed_data = self._preprocess_data(new_data)
        predictions = self.ensemble_model.predict(preprocessed_data)
        probabilities = self.ensemble_model.predict_proba(preprocessed_data)[:, 1]
        return predictions, probabilities

    def cross_validate_ensemble(self, features, labels, cv=5):
        logging.info(f"Performing {cv}-fold cross-validation for ensemble model...")
        preprocessed_features = self._preprocess_data(features)
        
        estimators = [(name, model) for name, model in self.base_models.items()]
        ensemble_cv = VotingClassifier(estimators=estimators, voting='soft', weights=[1, 1, 0.5, 1, 0.8])

        kf = KFold(n_splits=cv, shuffle=True, random_state=self.random_state)
        scores = cross_val_score(ensemble_cv, preprocessed_features, labels, cv=kf, scoring='roc_auc')
        
        logging.info(f"Cross-validation ROC AUC scores: {scores}")
        logging.info(f"Mean CV ROC AUC: {np.mean(scores):.4f} (+/- {np.std(scores) * 2:.4f})")
        return scores

    def save_model(self, path):
        logging.info(f"Saving ensemble model and preprocessors to {path}")
        model_components = {
            "ensemble_model": self.ensemble_model,
            "trained_base_models": self.trained_base_models,
            "scaler": self.scaler,
            "feature_columns": self.feature_columns
        }
        joblib.dump(model_components, path)

    def load_model(self, path):
        logging.info(f"Loading ensemble model and preprocessors from {path}")
        model_components = joblib.load(path)
        self.ensemble_model = model_components["ensemble_model"]
        self.trained_base_models = model_components["trained_base_models"]
        self.scaler = model_components["scaler"]
        self.feature_columns = model_components["feature_columns"]
        logging.info("Ensemble model loaded successfully.")

# Example Usage
if __name__ == '__main__':
    logging.info("--- Generating Dummy Data ---")
    num_samples = 2000
    # Generate more complex data with some correlation
    np.random.seed(42)
    data = {
        "feature1": np.random.rand(num_samples) * 100,
        "feature2": np.random.rand(num_samples) * 50,
        "feature3": np.random.normal(loc=50, scale=10, size=num_samples),
        "feature4": np.random.randint(0, 5, num_samples),
        "feature5": np.random.rand(num_samples) * 200,
    }
    df = pd.DataFrame(data)
    
    # Create a target variable with some noise and dependence on features
    df["target"] = ((df["feature1"] * 0.5 + df["feature2"] * 1.2 + df["feature3"] * 0.1) > 70).astype(int)
    # Introduce some fraud (target=1) that is harder to detect
    df.loc[np.random.choice(df.index, 50, replace=False), "target"] = 1
    
    # Add some categorical features for testing preprocessing
    df["category_feature"] = np.random.choice(["A", "B", "C"], num_samples)
    df = pd.get_dummies(df, columns=["category_feature"], drop_first=True)

    features = df.drop("target", axis=1)
    labels = df["target"]

    # Initialize and train the ensemble platform
    ensemble_platform = EnsembleModelPlatform()
    X_test, y_test = ensemble_platform.train_base_models(features, labels)
    ensemble_platform.train_ensemble_model(X_test, y_test)

    # Evaluate the ensemble model
    ensemble_platform.evaluate_ensemble(features, labels)

    # Perform cross-validation
    ensemble_platform.cross_validate_ensemble(features, labels)

    # Make predictions with the ensemble
    sample_data = pd.DataFrame({
        "feature1": [90, 10, 55],
        "feature2": [45, 5, 25],
        "feature3": [60, 40, 50],
        "feature4": [1, 4, 2],
        "feature5": [180, 20, 100],
        "category_feature_B": [0, 1, 0],
        "category_feature_C": [1, 0, 0]
    })
    predictions, probabilities = ensemble_platform.predict_with_ensemble(sample_data)
    logging.info(f"Sample predictions: {predictions}")
    logging.info(f"Sample probabilities: {probabilities}")

    # Save and load model
    model_path = "ensemble_fraud_model.joblib"
    ensemble_platform.save_model(model_path)
    
    loaded_ensemble = EnsembleModelPlatform()
    loaded_ensemble.load_model(model_path)
    loaded_predictions, _ = loaded_ensemble.predict_with_ensemble(sample_data)
    logging.info(f"Predictions from loaded model: {loaded_predictions}")

