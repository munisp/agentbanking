import shap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Tuple, Optional
import logging
from sklearn.inspection import permutation_importance
from sklearn.tree import DecisionTreeClassifier
import lime
import lime.lime_tabular
import warnings
import time
from typing import Dict, List, Optional, Any
import os
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ComprehensiveExplainabilityEngine:
    """
    A comprehensive explainability engine for fraud detection models.
    Provides multiple explanation methods including SHAP, LIME, and permutation importance.
    """

    
    def __init__(self, model, feature_names: List[str], model_type: str = "tree"):
        """
        Initialize the explainability engine.
        
        Args:
            model: Trained model to explain
            feature_names: List of feature names
            model_type: Type of model ('tree', 'linear', 'deep', 'ensemble')
        """

        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.explainers = {}
        self._initialize_explainers()
        
    def _initialize_explainers(self):
        """Initialize different explainer objects based on model type."""

        logging.info(f"Initializing explainers for {self.model_type} model...")
        
        try:
            if self.model_type in ["tree", "ensemble"]:
                self.explainers['shap'] = shap.TreeExplainer(self.model)
            elif self.model_type == "linear":
                self.explainers['shap'] = shap.LinearExplainer(self.model, np.zeros((1, len(self.feature_names))))
            else:
                # For deep learning or other models, use KernelExplainer
                self.explainers['shap'] = shap.KernelExplainer(self.model.predict_proba, np.zeros((1, len(self.feature_names))))
                
            logging.info("SHAP explainer initialized successfully")
        except Exception as e:
            logging.warning(f"Failed to initialize SHAP explainer: {e}")
    
    def explain_single_prediction(self, data_instance: np.ndarray, 
                                explanation_methods: List[str] = ["shap", "lime"]) -> Dict[str, Any]:
        """
        Explain a single prediction using multiple methods.
        
        Args:
            data_instance: Single data instance to explain
            explanation_methods: List of explanation methods to use
        
        Returns:
            Dictionary containing explanations from different methods
        """

        logging.info("Generating explanations for single prediction...")
        
        explanations = {}
        
        # Ensure data_instance is 2D
        if data_instance.ndim == 1:
            data_instance = data_instance.reshape(1, -1)
        
        # SHAP Explanation
        if "shap" in explanation_methods and 'shap' in self.explainers:
            try:
                shap_values = self.explainers['shap'].shap_values(data_instance)
                
                # Handle different SHAP output formats
                if isinstance(shap_values, list):
                    # For binary classification, use positive class
                    shap_values = shap_values[1] if len(shap_values) == 2 else shap_values[0]
                
                if shap_values.ndim > 1:
                    shap_values = shap_values[0]  # Take first instance
                
                feature_impact = pd.DataFrame({
                    'feature': self.feature_names[:len(shap_values)],
                    'shap_value': shap_values,
                    'feature_value': data_instance[0][:len(shap_values)]
                })
                feature_impact['abs_impact'] = np.abs(feature_impact['shap_value'])
                feature_impact = feature_impact.sort_values('abs_impact', ascending=False)
                
                explanations['shap'] = {
                    'feature_impacts': feature_impact,
                    'raw_shap_values': shap_values,
                    'expected_value': getattr(self.explainers['shap'], 'expected_value', 0)
                }
                
                logging.info("SHAP explanation generated successfully")
            except Exception as e:
                logging.error(f"Failed to generate SHAP explanation: {e}")
        
        # LIME Explanation
        if "lime" in explanation_methods:
            try:
                # Create LIME explainer
                lime_explainer = lime.lime_tabular.LimeTabularExplainer(
                    data_instance,
                    feature_names=self.feature_names[:data_instance.shape[1]],
                    class_names=['Normal', 'Fraud'],
                    mode='classification'
                )
                
                # Generate explanation
                lime_explanation = lime_explainer.explain_instance(
                    data_instance[0], 
                    self.model.predict_proba,
                    num_features=min(10, len(self.feature_names))
                )
                
                # Extract LIME results
                lime_features = []
                lime_values = []
                for feature, value in lime_explanation.as_list():
                    lime_features.append(feature)
                    lime_values.append(value)
                
                lime_df = pd.DataFrame({
                    'feature': lime_features,
                    'lime_value': lime_values
                })
                lime_df['abs_impact'] = np.abs(lime_df['lime_value'])
                lime_df = lime_df.sort_values('abs_impact', ascending=False)
                
                explanations['lime'] = {
                    'feature_impacts': lime_df,
                    'explanation_object': lime_explanation
                }
                
                logging.info("LIME explanation generated successfully")
            except Exception as e:
                logging.error(f"Failed to generate LIME explanation: {e}")
        
        # Permutation Importance
        if "permutation" in explanation_methods:
            try:
                # Create a simple dataset for permutation importance
                X_sample = np.tile(data_instance, (100, 1))  # Replicate instance
                y_sample = self.model.predict(X_sample)  # Get predictions
                
                perm_importance = permutation_importance(
                    self.model, X_sample, y_sample, 
                    n_repeats=10, random_state=42
                )
                
                perm_df = pd.DataFrame({
                    'feature': self.feature_names[:len(perm_importance.importances_mean)],
                    'importance_mean': perm_importance.importances_mean,
                    'importance_std': perm_importance.importances_std
                })
                perm_df = perm_df.sort_values('importance_mean', ascending=False)
                
                explanations['permutation'] = {
                    'feature_importance': perm_df,
                    'raw_importance': perm_importance
                }
                
                logging.info("Permutation importance generated successfully")
            except Exception as e:
                logging.error(f"Failed to generate permutation importance: {e}")
        
        return explanations
    
    def explain_batch_predictions(self, data_batch: np.ndarray, 
                                sample_size: int = 100) -> Dict[str, Any]:
        """
        Explain a batch of predictions and provide aggregate insights.
        
        Args:
            data_batch: Batch of data instances
            sample_size: Number of samples to explain (for performance)
        
Returns:
            Dictionary containing batch explanations and aggregated insights
        """

        logging.info(f"Generating batch explanations for {len(data_batch)} instances...")
        
        # Sample data if batch is too large
        if len(data_batch) > sample_size:
            indices = np.random.choice(len(data_batch), sample_size, replace=False)
            sample_data = data_batch[indices]
        else:
            sample_data = data_batch
        
        batch_explanations = []
        
        # Generate SHAP values for the batch
        try:
            if 'shap' in self.explainers:
                shap_values = self.explainers['shap'].shap_values(sample_data)
                
                # Handle different SHAP output formats
                if isinstance(shap_values, list):
                    shap_values = shap_values[1] if len(shap_values) == 2 else shap_values[0]
                
                # Calculate aggregate statistics
                mean_shap = np.mean(np.abs(shap_values), axis=0)
                std_shap = np.std(shap_values, axis=0)
                
                feature_importance_df = pd.DataFrame({
                    'feature': self.feature_names[:len(mean_shap)],
                    'mean_abs_shap': mean_shap,
                    'std_shap': std_shap,
                    'importance_rank': range(1, len(mean_shap) + 1)
                })
                feature_importance_df = feature_importance_df.sort_values('mean_abs_shap', ascending=False)
                feature_importance_df['importance_rank'] = range(1, len(feature_importance_df) + 1)
                
                batch_explanations.append({
                    'method': 'shap',
                    'feature_importance': feature_importance_df,
                    'raw_values': shap_values
                })
                
                logging.info("Batch SHAP explanations generated successfully")
        except Exception as e:
            logging.error(f"Failed to generate batch SHAP explanations: {e}")
        
        return {
            'batch_size': len(sample_data),
            'explanations': batch_explanations,
            'sample_indices': indices if len(data_batch) > sample_size else list(range(len(data_batch)))
        }
    
    def generate_global_explanations(self, X_train: np.ndarray, 
                                   y_train: np.ndarray = None) -> Dict[str, Any]:
        """
        Generate global model explanations.
        
        Args:
            X_train: Training data
            y_train: Training labels (optional)
        
        Returns:
            Dictionary containing global explanations
        """

        logging.info("Generating global model explanations...")
        
        global_explanations = {}
        
        # Feature Importance (if available)
        if hasattr(self.model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': self.feature_names[:len(self.model.feature_importances_)],
                'importance': self.model.feature_importances_
            })
            importance_df = importance_df.sort_values('importance', ascending=False)
            global_explanations['feature_importance'] = importance_df
        
        # Permutation Importance on training data
        if y_train is not None:
            try:
                perm_importance = permutation_importance(
                    self.model, X_train, y_train, 
                    n_repeats=5, random_state=42
                )
                
                perm_df = pd.DataFrame({
                    'feature': self.feature_names[:len(perm_importance.importances_mean)],
                    'importance_mean': perm_importance.importances_mean,
                    'importance_std': perm_importance.importances_std
                })
                perm_df = perm_df.sort_values('importance_mean', ascending=False)
                global_explanations['permutation_importance'] = perm_df
                
                logging.info("Global permutation importance generated")
            except Exception as e:
                logging.error(f"Failed to generate global permutation importance: {e}")
        
        # SHAP Summary (sample-based)
        try:
            if 'shap' in self.explainers:
                # Use a sample for efficiency
                sample_size = min(1000, len(X_train))
                sample_indices = np.random.choice(len(X_train), sample_size, replace=False)
                X_sample = X_train[sample_indices]
                
                shap_values = self.explainers['shap'].shap_values(X_sample)
                
                if isinstance(shap_values, list):
                    shap_values = shap_values[1] if len(shap_values) == 2 else shap_values[0]
                
                # Calculate global SHAP statistics
                global_shap_importance = np.mean(np.abs(shap_values), axis=0)
                
                shap_global_df = pd.DataFrame({
                    'feature': self.feature_names[:len(global_shap_importance)],
                    'global_shap_importance': global_shap_importance
                })
                shap_global_df = shap_global_df.sort_values('global_shap_importance', ascending=False)
                
                global_explanations['shap_global'] = {
                    'feature_importance': shap_global_df,
                    'sample_size': sample_size
                }
                
                logging.info("Global SHAP explanations generated")
        except Exception as e:
            logging.error(f"Failed to generate global SHAP explanations: {e}")
        
        return global_explanations
    
    def create_explanation_report(self, explanations: Dict[str, Any], 
                                prediction: float, prediction_proba: np.ndarray = None) -> str:
        """
        Create a human-readable explanation report.
        
        Args:
            explanations: Dictionary of explanations from different methods
            prediction: Model prediction
            prediction_proba: Prediction probabilities (optional)
        
        Returns:
            Formatted explanation report as string
        """

        report = []
        report.append("=== FRAUD DETECTION EXPLANATION REPORT ===\n")
        
        # Prediction summary
        report.append(f"Prediction: {'FRAUD' if prediction == 1 else 'NORMAL'}")
        if prediction_proba is not None:
            fraud_prob = prediction_proba[1] if len(prediction_proba) > 1 else prediction_proba[0]
            report.append(f"Fraud Probability: {fraud_prob:.3f}")
        report.append("")
        
        # SHAP Explanation
        if 'shap' in explanations:
            report.append("--- SHAP Analysis ---")
            shap_data = explanations['shap']['feature_impacts']
            top_features = shap_data.head(5)
            
            report.append("Top 5 Most Important Features:")
            for _, row in top_features.iterrows():
                direction = "increases" if row['shap_value'] > 0 else "decreases"
                report.append(f"  • {row['feature']}: {direction} fraud risk by {abs(row['shap_value']):.3f}")
                report.append(f"    Feature value: {row['feature_value']:.3f}")
            report.append("")
        
        # LIME Explanation
        if 'lime' in explanations:
            report.append("--- LIME Analysis ---")
            lime_data = explanations['lime']['feature_impacts']
            top_lime = lime_data.head(5)
            
            report.append("Top 5 Features (LIME):")
            for _, row in top_lime.iterrows():
                direction = "increases" if row['lime_value'] > 0 else "decreases"
                report.append(f"  • {row['feature']}: {direction} fraud probability")
            report.append("")
        
        # Risk Assessment
        report.append("--- Risk Assessment ---")
        if 'shap' in explanations:
            shap_data = explanations['shap']['feature_impacts']
            high_risk_features = shap_data[shap_data['shap_value'] > 0.1]
            
            if len(high_risk_features) > 0:
                report.append("High Risk Indicators:")
                for _, row in high_risk_features.iterrows():
                    report.append(f"  ⚠️  {row['feature']}: High impact on fraud risk")
            else:
                report.append("✅ No high-risk indicators detected")
        
        return "\n".join(report)
    
    def visualize_explanations(self, explanations: Dict[str, Any], 
                             save_path: str = None) -> plt.Figure:
        """
        Create visualizations for the explanations.
        
        Args:
            explanations: Dictionary of explanations
            save_path: Path to save the visualization (optional)
        
        Returns:
            Matplotlib figure object
        """

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Fraud Detection Model Explanations', fontsize=16, fontweight='bold')
        
        # SHAP Feature Importance
        if 'shap' in explanations:
            shap_data = explanations['shap']['feature_impacts'].head(10)
            axes[0, 0].barh(range(len(shap_data)), shap_data['abs_impact'])
            axes[0, 0].set_yticks(range(len(shap_data)))
            axes[0, 0].set_yticklabels(shap_data['feature'])
            axes[0, 0].set_xlabel('Absolute SHAP Value')
            axes[0, 0].set_title('SHAP Feature Importance')
            axes[0, 0].invert_yaxis()
        
        # LIME Feature Importance
        if 'lime' in explanations:
            lime_data = explanations['lime']['feature_impacts'].head(10)
            colors = ['red' if x < 0 else 'green' for x in lime_data['lime_value']]
            axes[0, 1].barh(range(len(lime_data)), lime_data['lime_value'], color=colors)
            axes[0, 1].set_yticks(range(len(lime_data)))
            axes[0, 1].set_yticklabels(lime_data['feature'])
            axes[0, 1].set_xlabel('LIME Value')
            axes[0, 1].set_title('LIME Feature Impact')
            axes[0, 1].invert_yaxis()
        
        # Feature Value Distribution (if SHAP available)
        if 'shap' in explanations:
            shap_data = explanations['shap']['feature_impacts'].head(10)
            axes[1, 0].scatter(shap_data['feature_value'], shap_data['shap_value'])
            axes[1, 0].set_xlabel('Feature Value')
            axes[1, 0].set_ylabel('SHAP Value')
            axes[1, 0].set_title('Feature Value vs SHAP Impact')
            
            # Add feature names as annotations
            for i, row in shap_data.iterrows():
                axes[1, 0].annotate(row['feature'][:10], 
                                  (row['feature_value'], row['shap_value']),
                                  fontsize=8, alpha=0.7)
        
        # Summary Statistics
        if 'shap' in explanations:
            shap_data = explanations['shap']['feature_impacts']
            summary_text = f"""
            Model Explanation Summary:
            
            Total Features Analyzed: {len(shap_data)}
            
            Top Risk Factor: {shap_data.iloc[0]['feature']}
            Max Impact: {shap_data.iloc[0]['abs_impact']:.3f}
            
            Positive Factors: {len(shap_data[shap_data['shap_value'] > 0])}
            Negative Factors: {len(shap_data[shap_data['shap_value'] < 0])}
            """

            
            axes[1, 1].text(0.1, 0.5, summary_text, fontsize=10, 
                           verticalalignment='center', transform=axes[1, 1].transAxes)
            axes[1, 1].set_title('Explanation Summary')
            axes[1, 1].axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logging.info(f"Explanation visualization saved to {save_path}")
        
        return fig

# --- Example Usage ---
if __name__ == "__main__":
    logging.info("--- Comprehensive Explainability Engine Example ---")
    
    # Create sample data and model for demonstration
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.datasets import make_classification
    
    # Generate sample data
    X, y = make_classification(n_samples=1000, n_features=20, n_informative=10, 
                             n_redundant=5, random_state=42)
    
    feature_names = [f'feature_{i}' for i in range(X.shape[1])]
    
    # Train a simple model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Initialize explainability engine
    explainer = ComprehensiveExplainabilityEngine(model, feature_names, "tree")
    
    # Test single prediction explanation
    test_instance = X[0]
    prediction = model.predict([test_instance])[0]
    prediction_proba = model.predict_proba([test_instance])[0]
    
    explanations = explainer.explain_single_prediction(test_instance, ["shap", "lime"])
    
    # Generate explanation report
    report = explainer.create_explanation_report(explanations, prediction, prediction_proba)
    print(report)
    
    # Test batch explanations
    batch_explanations = explainer.explain_batch_predictions(X[:100])
    logging.info(f"Generated batch explanations for {batch_explanations['batch_size']} instances")
    
    # Test global explanations
    global_explanations = explainer.generate_global_explanations(X, y)
    logging.info("Generated global model explanations")
    
    # Create visualization
    fig = explainer.visualize_explanations(explanations)
    plt.show()
    
    logging.info("Explainability engine example completed!")
