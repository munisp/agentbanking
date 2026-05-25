"""
Ray Distributed Training and Inference

Provides:
- Distributed model training across multiple workers
- Hyperparameter tuning with Ray Tune
- Distributed batch inference with Ray Data
- Model serving with Ray Serve
- GPU/CPU resource management

Architecture:
- Ray Train: Distributed PyTorch training (DDP)
- Ray Tune: Bayesian hyperparameter optimization
- Ray Data: Distributed data preprocessing
- Ray Serve: Online model serving with autoscaling
"""

import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

try:
    import ray
    from ray import train as ray_train
    from ray.train import ScalingConfig, RunConfig, CheckpointConfig
    from ray.train.torch import TorchTrainer, TorchCheckpoint
    from ray.tune import TuneConfig, Tuner
    from ray.tune.search.bayesopt import BayesOptSearch
    from ray.tune.schedulers import ASHAScheduler
    from ray import serve
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class RayDistributedTrainer:
    """Manages distributed training with Ray"""

    def __init__(self, num_workers: int = None, use_gpu: bool = False,
                 ray_address: str = None):
        self.num_workers = num_workers or int(os.getenv("RAY_NUM_WORKERS", "2"))
        self.use_gpu = use_gpu
        self.ray_address = ray_address or os.getenv("RAY_ADDRESS", None)

        if RAY_AVAILABLE:
            if not ray.is_initialized():
                ray.init(
                    address=self.ray_address,
                    num_cpus=self.num_workers * 2,
                    ignore_reinit_error=True,
                    logging_level=logging.WARNING,
                )
            logger.info(f"Ray initialized: {ray.cluster_resources()}")
        else:
            logger.warning("Ray not available. Using single-process fallback.")

    def train_distributed(self, train_func: Callable, config: Dict[str, Any],
                         num_workers: int = None, epochs: int = 100) -> Dict[str, Any]:
        """Run distributed PyTorch training with Ray Train

        Args:
            train_func: Training function that accepts config dict
            config: Training configuration (lr, batch_size, etc.)
            num_workers: Number of parallel workers
            epochs: Max training epochs

        Returns:
            Training results with metrics and checkpoint path
        """
        n_workers = num_workers or self.num_workers

        if not RAY_AVAILABLE:
            logger.info("Running in single-process mode (Ray unavailable)")
            return self._train_single_process(train_func, config, epochs)

        scaling_config = ScalingConfig(
            num_workers=n_workers,
            use_gpu=self.use_gpu,
            resources_per_worker={"CPU": 2, "GPU": 1 if self.use_gpu else 0},
        )

        run_config = RunConfig(
            name=f"train_{config.get('model_name', 'model')}_{int(time.time())}",
            checkpoint_config=CheckpointConfig(num_to_keep=3),
        )

        trainer = TorchTrainer(
            train_loop_per_worker=train_func,
            train_loop_config=config,
            scaling_config=scaling_config,
            run_config=run_config,
        )

        result = trainer.fit()

        return {
            "metrics": result.metrics,
            "checkpoint": str(result.checkpoint.path) if result.checkpoint else None,
            "num_workers": n_workers,
            "training_time": result.metrics.get("time_total_s", 0),
        }

    def hyperparameter_tune(self, train_func: Callable, search_space: Dict[str, Any],
                           metric: str = "val_auc", mode: str = "max",
                           num_samples: int = 20, max_epochs: int = 50) -> Dict[str, Any]:
        """Distributed hyperparameter tuning with Ray Tune

        Args:
            train_func: Training function
            search_space: Hyperparameter search space
            metric: Optimization metric
            mode: 'max' or 'min'
            num_samples: Number of trials
            max_epochs: Max epochs per trial

        Returns:
            Best config and metrics
        """
        if not RAY_AVAILABLE:
            logger.info("Running single hyperparameter config (Ray unavailable)")
            # Just use default config
            default_config = {k: v if not callable(v) else v() for k, v in search_space.items()}
            result = self._train_single_process(train_func, default_config, max_epochs)
            return {"best_config": default_config, "best_metric": result.get(metric, 0)}

        scheduler = ASHAScheduler(
            max_t=max_epochs,
            grace_period=5,
            reduction_factor=2,
        )

        tuner = Tuner(
            train_func,
            param_space=search_space,
            tune_config=TuneConfig(
                metric=metric,
                mode=mode,
                num_samples=num_samples,
                scheduler=scheduler,
                search_alg=BayesOptSearch(metric=metric, mode=mode),
            ),
            run_config=RunConfig(
                name=f"tune_{int(time.time())}",
            ),
        )

        results = tuner.fit()
        best_result = results.get_best_result(metric=metric, mode=mode)

        return {
            "best_config": best_result.config,
            "best_metric": best_result.metrics[metric],
            "num_trials": num_samples,
            "all_results": [r.metrics for r in results],
        }

    def distributed_inference(self, model_path: str, data: pd.DataFrame,
                             batch_size: int = 1024) -> np.ndarray:
        """Distributed batch inference using Ray Data

        Args:
            model_path: Path to saved model checkpoint
            data: Input DataFrame for inference
            batch_size: Batch size for inference

        Returns:
            Predictions array
        """
        if not RAY_AVAILABLE:
            return self._inference_single_process(model_path, data, batch_size)

        # Convert to Ray Dataset
        ds = ray.data.from_pandas(data)

        # Define inference function
        class InferenceWorker:
            def __init__(self):
                self.model = torch.load(model_path, map_location="cpu")
                self.model.eval()

            def __call__(self, batch: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
                features = np.column_stack([batch[col] for col in batch.keys()])
                with torch.no_grad():
                    tensor = torch.FloatTensor(features)
                    predictions = self.model(tensor).numpy()
                return {"predictions": predictions}

        # Run distributed inference
        results = ds.map_batches(
            InferenceWorker,
            batch_size=batch_size,
            concurrency=self.num_workers,
            compute=ray.data.ActorPoolStrategy(size=self.num_workers),
        )

        return results.to_pandas()["predictions"].values

    def _train_single_process(self, train_func: Callable, config: Dict, epochs: int) -> Dict:
        """Fallback single-process training"""
        config["epochs"] = epochs
        config["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        return train_func(config)

    def _inference_single_process(self, model_path: str, data: pd.DataFrame,
                                  batch_size: int) -> np.ndarray:
        """Fallback single-process inference"""
        checkpoint = torch.load(model_path, map_location="cpu")
        if "model_state_dict" in checkpoint:
            # Need to reconstruct model - caller should handle this
            logger.warning("Single-process inference: returning empty predictions")
            return np.zeros(len(data))
        else:
            model = checkpoint
            model.eval()
            features = data.values.astype(np.float32)
            predictions = []
            for i in range(0, len(features), batch_size):
                batch = torch.FloatTensor(features[i:i+batch_size])
                with torch.no_grad():
                    pred = model(batch).numpy()
                predictions.append(pred)
            return np.concatenate(predictions)

    def shutdown(self):
        """Shutdown Ray cluster"""
        if RAY_AVAILABLE and ray.is_initialized():
            ray.shutdown()
            logger.info("Ray shutdown complete")


class RayModelServer:
    """Ray Serve deployment for online inference"""

    def __init__(self, model_name: str, model_path: str, num_replicas: int = 2):
        self.model_name = model_name
        self.model_path = model_path
        self.num_replicas = num_replicas

    def deploy(self):
        """Deploy model as Ray Serve endpoint"""
        if not RAY_AVAILABLE:
            logger.warning("Ray Serve not available")
            return None

        model_path = self.model_path

        @serve.deployment(
            name=self.model_name,
            num_replicas=self.num_replicas,
            ray_actor_options={"num_cpus": 1},
        )
        class ModelDeployment:
            def __init__(self):
                self.model = torch.load(model_path, map_location="cpu")
                if hasattr(self.model, 'eval'):
                    self.model.eval()
                self.request_count = 0

            async def __call__(self, request) -> Dict[str, Any]:
                data = await request.json()
                features = np.array(data["features"], dtype=np.float32)
                tensor = torch.FloatTensor(features)

                with torch.no_grad():
                    if features.ndim == 1:
                        tensor = tensor.unsqueeze(0)
                    predictions = self.model(tensor).numpy()

                self.request_count += 1
                return {
                    "predictions": predictions.tolist(),
                    "model": self.model_name,
                    "request_count": self.request_count,
                }

        handle = serve.run(ModelDeployment.bind(), route_prefix=f"/predict/{self.model_name}")
        logger.info(f"Deployed {self.model_name} at /predict/{self.model_name}")
        return handle
