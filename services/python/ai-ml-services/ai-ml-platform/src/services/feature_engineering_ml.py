import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.decomposition import PCA
import networkx as nx
import logging
import joblib

import time
from datetime import datetime
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AdvancedFeatureEngineer:
    """A comprehensive feature engineering pipeline for fraud detection."""

    def __init__(self, n_components_pca=5):
        self.scaler = StandardScaler()
        self.one_hot_encoder = OneHotEncoder(handle_unknown='ignore')
        self.pca = PCA(n_components=n_components_pca)
        self.graph_features_calculator = GraphFeatures()
        self.temporal_features_calculator = TemporalFeatures()
        self.behavioral_features_calculator = BehavioralFeatures()

    def fit_transform(self, transactions_df, user_profiles_df, networks_df, behavioral_df):
        logging.info("Starting feature engineering process...")

        # 1. Initial Data Merging and Cleaning
        df = self.initial_merge(transactions_df, user_profiles_df)

        # 2. Temporal Features
        df = self.temporal_features_calculator.create_features(df)

        # 3. Behavioral Features
        behavioral_features = self.behavioral_features_calculator.create_features(behavioral_df)
        df = df.merge(behavioral_features, on='user_id', how='left').fillna(0)

        # 4. Graph/Network Features
        graph_features = self.graph_features_calculator.create_features(networks_df)
        df = df.merge(graph_features, on='user_id', how='left').fillna(0)

        # 5. Interaction and Aggregation Features
        df = self.create_interaction_features(df)
        df = self.create_aggregation_features(df)

        # 6. Categorical Feature Encoding
        categorical_cols = [col for col in df.columns if df[col].dtype == 'object' and col not in ['transaction_id', 'user_id']]
        # For simplicity, we assume there are some categorical features to encode
        # In a real scenario, you would select them carefully.
        # Let's create a dummy one for the example
        df['device_type'] = np.random.choice(['mobile', 'desktop', 'tablet'], len(df))
        categorical_cols.append('device_type')

        encoded_cats = self.one_hot_encoder.fit_transform(df[categorical_cols])
        encoded_cat_df = pd.DataFrame(encoded_cats.toarray(), columns=self.one_hot_encoder.get_feature_names_out(categorical_cols))
        df = df.drop(categorical_cols, axis=1).reset_index(drop=True)
        df = pd.concat([df, encoded_cat_df], axis=1)

        # 7. Numerical Feature Scaling
        numerical_cols = [col for col in df.columns if df[col].dtype in ['int64', 'float64'] and col not in ['transaction_id', 'user_id']]
        df[numerical_cols] = self.scaler.fit_transform(df[numerical_cols])

        # 8. Dimensionality Reduction (Optional)
        # Apply PCA to reduce dimensionality if needed
        # df_pca = self.pca.fit_transform(df[numerical_cols])
        # pca_df = pd.DataFrame(df_pca, columns=[f'pca_{i}' for i in range(self.pca.n_components_)])
        # df = pd.concat([df[['transaction_id', 'user_id']], pca_df], axis=1)

        logging.info(f"Feature engineering completed. Final shape: {df.shape}")
        return df

    def transform(self, transactions_df, user_profiles_df, networks_df, behavioral_df):
        """Transform method for inference - applies fitted transformers without refitting."""

        logging.info("Starting feature transformation for inference...")

        # 1. Initial Data Merging and Cleaning
        df = self.initial_merge(transactions_df, user_profiles_df)

        # 2. Temporal Features
        df = self.temporal_features_calculator.create_features(df)

        # 3. Behavioral Features
        behavioral_features = self.behavioral_features_calculator.create_features(behavioral_df)
        df = df.merge(behavioral_features, on='user_id', how='left').fillna(0)

        # 4. Graph/Network Features
        graph_features = self.graph_features_calculator.create_features(networks_df)
        df = df.merge(graph_features, on='user_id', how='left').fillna(0)

        # 5. Interaction and Aggregation Features
        df = self.create_interaction_features(df)
        df = self.create_aggregation_features(df)

        # 6. Categorical Feature Encoding (using fitted encoder)
        categorical_cols = [col for col in df.columns if df[col].dtype == 'object' and col not in ['transaction_id', 'user_id']]
        df['device_type'] = np.random.choice(['mobile', 'desktop', 'tablet'], len(df))
        categorical_cols.append('device_type')

        encoded_cats = self.one_hot_encoder.transform(df[categorical_cols])
        encoded_cat_df = pd.DataFrame(encoded_cats.toarray(), columns=self.one_hot_encoder.get_feature_names_out(categorical_cols))
        df = df.drop(categorical_cols, axis=1).reset_index(drop=True)
        df = pd.concat([df, encoded_cat_df], axis=1)

        # 7. Numerical Feature Scaling (using fitted scaler)
        numerical_cols = [col for col in df.columns if df[col].dtype in ['int64', 'float64'] and col not in ['transaction_id', 'user_id']]
        df[numerical_cols] = self.scaler.transform(df[numerical_cols])

        logging.info(f"Feature transformation completed. Final shape: {df.shape}")
        return df

    def initial_merge(self, transactions_df, user_profiles_df):
        df = transactions_df.merge(user_profiles_df, left_on='sender_id', right_on='user_id', how='left')
        df = df.merge(user_profiles_df, left_on='receiver_id', right_on='user_id', how='left', suffixes=('_sender', '_receiver'))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.fillna(0)

    def create_interaction_features(self, df):
        # Create interaction features between different variables
        df['amount_per_hour'] = df['amount'] / (df['hour_of_day'] + 1)  # Add 1 to avoid division by zero
        df['amount_velocity'] = df['amount'] / (df.groupby('sender_id')['timestamp'].diff().dt.total_seconds().fillna(3600) + 1)
        return df

    def create_aggregation_features(self, df):
        # Create aggregation features
        df['sender_total_amount'] = df.groupby('sender_id')['amount'].transform('sum')
        df['sender_avg_amount'] = df.groupby('sender_id')['amount'].transform('mean')
        df['sender_transaction_count'] = df.groupby('sender_id').cumcount() + 1
        return df

    def save_preprocessors(self, filepath):
        preprocessors = {
            'scaler': self.scaler,
            'one_hot_encoder': self.one_hot_encoder,
            'pca': self.pca
        }
        joblib.dump(preprocessors, filepath)
        logging.info(f"Preprocessors saved to {filepath}")

    def load_preprocessors(self, filepath):
        preprocessors = joblib.load(filepath)
        self.scaler = preprocessors['scaler']
        self.one_hot_encoder = preprocessors['one_hot_encoder']
        self.pca = preprocessors['pca']
        logging.info(f"Preprocessors loaded from {filepath}")

class GraphFeatures:
    def create_features(self, networks_df):
        # Create a graph from the networks data
        G = nx.from_pandas_edgelist(networks_df, source='user_a', target='user_b')
        
        features = []
        for user_id in networks_df['user_a'].unique():
            if user_id in G:
                degree = G.degree(user_id)
                try:
                    betweenness = nx.betweenness_centrality(G)[user_id]
                    closeness = nx.closeness_centrality(G)[user_id]
                except:
                    betweenness = 0
                    closeness = 0
                
                features.append({
                    'user_id': user_id,
                    'degree_centrality': degree,
                    'betweenness_centrality': betweenness,
                    'closeness_centrality': closeness
                })
            else:
                features.append({
                    'user_id': user_id,
                    'degree_centrality': 0,
                    'betweenness_centrality': 0,
                    'closeness_centrality': 0
                })
        
        return pd.DataFrame(features)

class TemporalFeatures:
    def create_features(self, df):
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['month'] = df['timestamp'].dt.month
        return df

class BehavioralFeatures:
    def create_features(self, behavioral_df):
        # Aggregate behavioral features by user
        features = behavioral_df.groupby('user_id').agg({
            'session_duration': ['mean', 'std', 'max'],
            'pages_visited': ['mean', 'sum'],
            'clicks': ['mean', 'sum']
        }).reset_index()
        
        # Flatten column names
        features.columns = ['user_id'] + ['_'.join(col).strip() for col in features.columns[1:]]
        return features.fillna(0)

# --- Example Usage ---
if __name__ == "__main__":
    logging.info("--- Advanced Feature Engineering Example ---")
    
    # Create sample data for demonstration
    transactions_df = pd.DataFrame({
        'transaction_id': range(1000),
        'sender_id': np.random.randint(1, 101, 1000),
        'receiver_id': np.random.randint(1, 101, 1000),
        'amount': np.random.exponential(100, 1000),
        'timestamp': pd.date_range('2023-01-01', periods=1000, freq='H')
    })
    
    user_profiles_df = pd.DataFrame({
        'user_id': range(1, 101),
        'age': np.random.randint(18, 80, 100),
        'account_balance': np.random.exponential(1000, 100)
    })
    
    networks_df = pd.DataFrame({
        'user_a': np.random.randint(1, 101, 500),
        'user_b': np.random.randint(1, 101, 500),
        'connection_strength': np.random.random(500)
    })
    
    behavioral_df = pd.DataFrame({
        'user_id': np.random.randint(1, 101, 2000),
        'session_duration': np.random.exponential(300, 2000),
        'pages_visited': np.random.poisson(5, 2000),
        'clicks': np.random.poisson(10, 2000)
    })

    feature_engineer = AdvancedFeatureEngineer()
    engineered_df = feature_engineer.fit_transform(transactions_df, user_profiles_df, networks_df, behavioral_df)

    logging.info(f"Engineered dataframe head:\n{engineered_df.head()}")
    logging.info(f"Engineered dataframe info:")
    engineered_df.info()

    # Save preprocessors
    feature_engineer.save_preprocessors('advanced_feature_preprocessors.joblib')
    logging.info("Feature engineering example completed successfully!")
