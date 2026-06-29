import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, precision_recall_fscore_support
import logging
import joblib
import time
from collections import deque

import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AnomalyDetector:
    """A robust, multi-model anomaly detection service."""

    def __init__(self, model_type='isolation_forest', contamination=0.05, **kwargs):
        self.model_type = model_type
        self.contamination = contamination
        self.model = self._initialize_model(kwargs)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_cols = None

    def _initialize_model(self, kwargs):
        logging.info(f"Initializing anomaly detection model: {self.model_type}")
        if self.model_type == 'isolation_forest':
            return IsolationForest(contamination=self.contamination, random_state=42, n_estimators=kwargs.get('n_estimators', 100))
        elif self.model_type == 'lof':
            # LOF's novelty=True makes it suitable for anomaly detection on new data
            return LocalOutlierFactor(contamination=self.contamination, novelty=True, n_neighbors=kwargs.get('n_neighbors', 20))
        elif self.model_type == 'one_class_svm':
            return OneClassSVM(nu=self.contamination, kernel=kwargs.get('kernel', 'rbf'), gamma=kwargs.get('gamma', 'auto'))
        else:
            raise ValueError("Unsupported model type. Choose from 'isolation_forest', 'lof', 'one_class_svm'.")

    def train(self, data_df, feature_cols):
        if not isinstance(data_df, pd.DataFrame) or data_df.empty:
            raise ValueError("Input data for training must be a non-empty pandas DataFrame.")
        
        self.feature_cols = feature_cols
        logging.info(f"Training {self.model_type} on {len(data_df)} samples with features: {self.feature_cols}")

        # Preprocess data
        features = data_df[self.feature_cols].copy()
        features.fillna(features.median(), inplace=True) # Handle missing values
        scaled_features = self.scaler.fit_transform(features)

        # Train the model
        self.model.fit(scaled_features)
        self.is_trained = True
        logging.info("Anomaly detector trained successfully.")

    def predict(self, new_data_df):
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() before making predictions.")
        if not isinstance(new_data_df, pd.DataFrame) or new_data_df.empty:
            raise ValueError("Input data for prediction must be a non-empty pandas DataFrame.")

        logging.info(f"Predicting anomalies on {len(new_data_df)} new samples.")
        
        features = new_data_df[self.feature_cols].copy()
        features.fillna(features.median(), inplace=True)
        scaled_features = self.scaler.transform(features)

        predictions = self.model.predict(scaled_features)
        # Convert predictions to a standard format: 1 for anomaly, 0 for normal
        return np.where(predictions == -1, 1, 0)

    def get_anomaly_scores(self, new_data_df):
        """Returns a score indicating the degree of abnormality."""
        if not self.is_trained:
            raise RuntimeError("Model not trained.")
        
        features = new_data_df[self.feature_cols].copy()
        features.fillna(features.median(), inplace=True)
        scaled_features = self.scaler.transform(features)

        if hasattr(self.model, 'decision_function'):
            # Lower scores are more abnormal for IsolationForest and OneClassSVM
            scores = self.model.decision_function(scaled_features)
            return -scores # Invert so higher scores mean more anomalous
        elif hasattr(self.model, 'negative_outlier_factor_'):
            # LOF provides this after fitting. For new data, we can use a workaround or re-fit.
            # For simplicity in prediction, let's just return the prediction.
            logging.warning("LOF does not provide a direct scoring method for new data in this implementation.")
            return self.predict(new_data_df) 
        else:
            raise AttributeError("Model does not support anomaly scoring.")

    def save_model(self, path):
        logging.info(f"Saving anomaly detection model and scaler to {path}")
        joblib.dump({'model': self.model, 'scaler': self.scaler, 'features': self.feature_cols}, path)

    def load_model(self, path):
        logging.info(f"Loading anomaly detection model and scaler from {path}")
        components = joblib.load(path)
        self.model = components['model']
        self.scaler = components['scaler']
        self.feature_cols = components['features']
        self.is_trained = True
        logging.info("Model loaded successfully.")

class ModelEvaluator:
    """Evaluates the performance of anomaly detection models."""

    def evaluate(self, data_df, feature_cols, true_labels=None):
        scaled_features = StandardScaler().fit_transform(data_df[feature_cols].fillna(data_df[feature_cols].median()))
        
        if true_labels is not None:
            # Supervised evaluation
            logging.info("Performing supervised evaluation...")
            model = AnomalyDetector() # Using default IsolationForest
            model.train(data_df, feature_cols)
            predictions = model.predict(data_df)
            
            precision, recall, f1, _ = precision_recall_fscore_support(true_labels, predictions, average='binary')
            logging.info(f"Precision: {precision:.4f}, Recall: {recall:.4f}, F1-Score: {f1:.4f}")
            return {"precision": precision, "recall": recall, "f1_score": f1}
        else:
            # Unsupervised evaluation
            logging.info("Performing unsupervised evaluation using Silhouette Score...")
            # This is tricky as we need predictions to evaluate.
            # Let's assume we have predictions from some model.
            temp_model = IsolationForest(contamination=0.05).fit(scaled_features)
            predictions = temp_model.predict(scaled_features)
            
            if len(np.unique(predictions)) > 1:
                score = silhouette_score(scaled_features, predictions)
                logging.info(f"Silhouette Score: {score:.4f}")
                return {"silhouette_score": score}
            else:
                logging.warning("Only one cluster found. Cannot compute Silhouette Score.")
                return {"silhouette_score": None}

class StreamingAnomalyDetector:
    """Detects anomalies in a real-time stream of data."""

    def __init__(self, window_size=1000, retrain_threshold=0.1, contamination=0.05):
        self.window = deque(maxlen=window_size)
        self.retrain_threshold = retrain_threshold
        self.model = IsolationForest(contamination=contamination)
        self.scaler = StandardScaler()
        self.is_ready = False
        self.processed_count = 0
        self.anomaly_count_in_window = 0

    def process_transaction(self, transaction):
        """Process a single transaction and return if it's an anomaly."""

        self.window.append(transaction)
        self.processed_count += 1

        if len(self.window) < self.window.maxlen and not self.is_ready:
            # Still filling the initial window
            return None, "Filling initial window..."

        if not self.is_ready or self._should_retrain():
            self._train_on_window()

        # Predict the new transaction
        features = pd.DataFrame([transaction])
        scaled_features = self.scaler.transform(features)
        prediction = self.model.predict(scaled_features)[0]
        is_anomaly = 1 if prediction == -1 else 0

        if is_anomaly:
            self.anomaly_count_in_window += 1
        
        return is_anomaly, "Prediction complete"

    def _train_on_window(self):
        logging.info("Training/retraining streaming anomaly detector on current window...")
        window_df = pd.DataFrame(list(self.window))
        scaled_features = self.scaler.fit_transform(window_df)
        self.model.fit(scaled_features)
        self.is_ready = True
        self.anomaly_count_in_window = 0 # Reset anomaly count after retraining
        logging.info("Streaming model is ready.")

    def _should_retrain(self):
        """Check if the model should be retrained based on concept drift."""
        if not self.is_ready:
            return False
        
        anomaly_rate = self.anomaly_count_in_window / len(self.window)
        # Retrain if the anomaly rate deviates significantly from the expected contamination rate
        if abs(anomaly_rate - self.model.contamination) > self.retrain_threshold:
            logging.warning(f"Concept drift detected! Anomaly rate: {anomaly_rate:.2f}. Retraining model.")
            return True
        return False

# Example Usage
if __name__ == '__main__':
    # 1. Generate more realistic dummy data
    logging.info("--- Generating Dummy Data ---")
    num_samples = 2000
    data = {
        'amount': np.random.lognormal(mean=3, sigma=1, size=num_samples),
        'time_since_last_tx': np.random.exponential(scale=100, size=num_samples),
        'user_avg_amount': np.random.lognormal(mean=4, sigma=1.5, size=num_samples)
    }
    df = pd.DataFrame(data)

    # Inject some anomalies
    num_anomalies = int(num_samples * 0.05)
    anomaly_indices = np.random.choice(df.index, num_anomalies, replace=False)
    df.loc[anomaly_indices, 'amount'] *= np.random.uniform(5, 15, num_anomalies)
    df.loc[anomaly_indices, 'time_since_last_tx'] = np.random.uniform(0, 5, num_anomalies)
    true_labels = np.zeros(num_samples)
    true_labels[anomaly_indices] = 1

    feature_cols = ['amount', 'time_since_last_tx', 'user_avg_amount']

    # 2. Train and Evaluate different models
    logging.info("--- Training and Evaluating Models ---")
    
    # Isolation Forest
    iso_forest = AnomalyDetector(model_type='isolation_forest', contamination=0.05)
    iso_forest.train(df, feature_cols)
    iso_preds = iso_forest.predict(df)
    p, r, f1, _ = precision_recall_fscore_support(true_labels, iso_preds, average='binary')
    logging.info(f"Isolation Forest -> F1: {f1:.4f}, Precision: {p:.4f}, Recall: {r:.4f}")

    # Local Outlier Factor
    lof = AnomalyDetector(model_type='lof', contamination=0.05)
    lof.train(df, feature_cols)
    lof_preds = lof.predict(df)
    p, r, f1, _ = precision_recall_fscore_support(true_labels, lof_preds, average='binary')
    logging.info(f"Local Outlier Factor -> F1: {f1:.4f}, Precision: {p:.4f}, Recall: {r:.4f}")

    # 3. Save and Load the best model (let's assume it's Isolation Forest)
    logging.info("--- Saving and Loading Model ---")
    model_path = 'anomaly_detector.joblib'
    iso_forest.save_model(model_path)

    loaded_detector = AnomalyDetector()
    loaded_detector.load_model(model_path)
    loaded_preds = loaded_detector.predict(df.head(10))
    logging.info(f"Predictions from loaded model (first 10): {loaded_preds}")

    # 4. Use the Model Evaluator
    logging.info("--- Using Model Evaluator ---")
    evaluator = ModelEvaluator()
    # Supervised
    evaluator.evaluate(df, feature_cols, true_labels=true_labels)
    # Unsupervised
    evaluator.evaluate(df, feature_cols)

    # 5. Demonstrate Streaming Anomaly Detection
    logging.info("--- Demonstrating Streaming Detector ---")
    streaming_detector = StreamingAnomalyDetector(window_size=500, retrain_threshold=0.05)
    
    for i, row in df.iterrows():
        transaction = row[feature_cols].to_dict()
        is_anomaly, status = streaming_detector.process_transaction(transaction)
        if (i + 1) % 200 == 0:
            logging.info(f"Processed transaction {i+1}. Status: {status}. Anomaly: {is_anomaly}")
    
    logging.info("Full demonstration complete.")

