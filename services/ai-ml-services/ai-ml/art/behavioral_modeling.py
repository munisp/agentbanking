import pandas as pd
import numpy as np
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
import logging
import joblib

import time
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BehavioralModeler:
    """A sophisticated platform for user segmentation based on behavioral patterns."""


    def __init__(self, model_type='kmeans', n_clusters=5, **kwargs):
        self.model_type = model_type
        self.n_clusters = n_clusters
        self.model = self._initialize_model(kwargs)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_cols = None

    def _initialize_model(self, kwargs):
        logging.info(f"Initializing behavioral modeling with {self.model_type}...")
        if self.model_type == 'kmeans':
            return KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        elif self.model_type == 'dbscan':
            return DBSCAN(eps=kwargs.get('eps', 0.5), min_samples=kwargs.get('min_samples', 5))
        elif self.model_type == 'gmm':
            return GaussianMixture(n_components=self.n_clusters, random_state=42)
        elif self.model_type == 'agglomerative':
            return AgglomerativeClustering(n_clusters=self.n_clusters)
        else:
            raise ValueError("Unsupported model type. Choose from 'kmeans', 'dbscan', 'gmm', 'agglomerative'.")

    def train(self, user_profiles_df, feature_cols):
        if not isinstance(user_profiles_df, pd.DataFrame) or user_profiles_df.empty:
            raise ValueError("User profiles data must be a non-empty pandas DataFrame.")
        
        self.feature_cols = feature_cols
        logging.info(f"Training {self.model_type} on {len(user_profiles_df)} users with features: {self.feature_cols}")

        features = user_profiles_df[self.feature_cols].copy().fillna(0)
        scaled_features = self.scaler.fit_transform(features)

        self.model.fit(scaled_features)
        self.is_trained = True
        logging.info("Behavioral modeler trained successfully.")

        # Evaluate the clustering performance
        self.evaluate_clustering(scaled_features)

    def predict_user_segment(self, user_profile_df):
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        if not isinstance(user_profile_df, pd.DataFrame) or user_profile_df.empty:
            raise ValueError("User profile data for prediction must be a non-empty DataFrame.")

        logging.info(f"Segmenting {len(user_profile_df)} new users.")
        features = user_profile_df[self.feature_cols].copy().fillna(0)
        scaled_features = self.scaler.transform(features)

        return self.model.predict(scaled_features)

    def evaluate_clustering(self, scaled_features):
        logging.info("Evaluating clustering performance...")
        labels = self.model.labels_ if hasattr(self.model, 'labels_') else self.model.predict(scaled_features)
        
        if len(np.unique(labels)) > 1:
            silhouette = silhouette_score(scaled_features, labels)
            calinski = calinski_harabasz_score(scaled_features, labels)
            davies = davies_bouldin_score(scaled_features, labels)
            logging.info(f"Silhouette Score: {silhouette:.4f}")
            logging.info(f"Calinski-Harabasz Score: {calinski:.4f}")
            logging.info(f"Davies-Bouldin Score: {davies:.4f}")
            return {"silhouette": silhouette, "calinski_harabasz": calinski, "davies_bouldin": davies}
        else:
            logging.warning("Only one cluster found. Cannot compute evaluation metrics.")
            return None

    def find_optimal_clusters(self, data_df, feature_cols, max_clusters=10):
        if self.model_type not in ['kmeans', 'gmm', 'agglomerative']:
            logging.warning(f"Optimal cluster search not applicable for {self.model_type}.")
            return

        logging.info(f"Finding optimal number of clusters (up to {max_clusters})...")
        features = data_df[feature_cols].copy().fillna(0)
        scaled_features = self.scaler.fit_transform(features)

        silhouette_scores = []
        for k in range(2, max_clusters + 1):
            if self.model_type == 'kmeans':
                model = KMeans(n_clusters=k, random_state=42, n_init=10).fit(scaled_features)
            elif self.model_type == 'gmm':
                model = GaussianMixture(n_components=k, random_state=42).fit(scaled_features)
            elif self.model_type == 'agglomerative':
                model = AgglomerativeClustering(n_clusters=k).fit(scaled_features)
            
            labels = model.labels_ if hasattr(model, 'labels_') else model.predict(scaled_features)
            if len(np.unique(labels)) > 1:
                score = silhouette_score(scaled_features, labels)
                silhouette_scores.append(score)
                logging.info(f"For n_clusters = {k}, Silhouette Score is {score:.4f}")
        
        if silhouette_scores:
            optimal_k = np.argmax(silhouette_scores) + 2 # +2 because range starts at 2
            logging.info(f"Optimal number of clusters found: {optimal_k}")
            return optimal_k
        return None

    def save_model(self, path):
        logging.info(f"Saving behavioral model and preprocessors to {path}")
        model_components = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_cols': self.feature_cols
        }
        joblib.dump(model_components, path)

    def load_model(self, path):
        logging.info(f"Loading behavioral model from {path}")
        model_components = joblib.load(path)
        self.model = model_components['model']
        self.scaler = model_components['scaler']
        self.feature_cols = model_components['feature_cols']
        self.is_trained = True
        logging.info("Behavioral model loaded successfully.")

# Example Usage
if __name__ == '__main__':
    logging.info("--- Generating Dummy User Profile Data ---")
    num_users = 1000
    user_data = {
        'user_id': [f'user_{i}' for i in range(num_users)],
        'avg_transaction_amount': np.random.lognormal(mean=4, sigma=1, size=num_users),
        'transaction_frequency': np.random.randint(1, 100, num_users),
        'session_duration_avg': np.random.exponential(scale=300, size=num_users),
        'num_devices_used': np.random.randint(1, 5, num_users),
        'age': np.random.randint(18, 70, num_users)
    }
    user_profiles_df = pd.DataFrame(user_data)

    feature_cols = ['avg_transaction_amount', 'transaction_frequency', 'session_duration_avg', 'num_devices_used', 'age']

    # 1. Find optimal number of clusters
    temp_modeler = BehavioralModeler()
    optimal_k = temp_modeler.find_optimal_clusters(user_profiles_df, feature_cols)

    # 2. Train the model with the optimal k
    if optimal_k:
        modeler = BehavioralModeler(n_clusters=optimal_k)
        modeler.train(user_profiles_df, feature_cols)

        # 3. Predict segments for new users
        new_users_data = {
            'user_id': [f'new_user_{i}' for i in range(5)],
            'avg_transaction_amount': [100, 5000, 250, 800, 1200],
            'transaction_frequency': [5, 80, 12, 40, 60],
            'session_duration_avg': [120, 600, 200, 400, 500],
            'num_devices_used': [1, 3, 1, 2, 2],
            'age': [25, 45, 30, 55, 38]
        }
        new_users_df = pd.DataFrame(new_users_data)
        segments = modeler.predict_user_segment(new_users_df)
        logging.info(f"Segments for new users: {segments}")

        # 4. Save and load the model
        model_path = 'behavioral_model.joblib'
        modeler.save_model(model_path)

        loaded_modeler = BehavioralModeler()
        loaded_modeler.load_model(model_path)
        loaded_segments = loaded_modeler.predict_user_segment(new_users_df)
        logging.info(f"Segments from loaded model: {loaded_segments}")

        # 5. Analyze cluster characteristics
        user_profiles_df['segment'] = modeler.model.labels_
        segment_summary = user_profiles_df.groupby('segment')[feature_cols].mean()
        logging.info(f"Segment characteristics:\n{segment_summary}")

