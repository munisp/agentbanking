import torch
import torch.nn as nn
import numpy as np
import time
import logging
from typing import Dict, Any, List, Tuple
import onnx
import onnxruntime as ort
from torch.quantization import quantize_dynamic
import pickle

class RestrictedUnpickler(pickle.Unpickler):
    """Restrict pickle to safe built-in types only."""
    SAFE_MODULES = {"builtins", "collections", "numpy", "torch"}
    def find_class(self, module, name):
        if module.split(".")[0] not in self.SAFE_MODULES:
            raise pickle.UnpicklingError(f"Blocked: {module}.{name}")
        return super().find_class(module, name)
import joblib

from typing import Dict, List, Optional, Any
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InferenceOptimizer:
    """
    A comprehensive inference optimization service for ML models.
    Provides various optimization techniques including TorchScript, ONNX, quantization, and batching.
    """

    
    def __init__(self):
        self.optimized_models = {}
        self.optimization_stats = {}
        
    def optimize_pytorch_model(self, model: nn.Module, example_input: torch.Tensor, 
                             optimization_type: str = "torchscript") -> Dict[str, Any]:
        """
        Optimize a PyTorch model using various techniques.
        
        Args:
            model: PyTorch model to optimize
            example_input: Example input tensor for tracing
            optimization_type: Type of optimization ('torchscript', 'quantization', 'onnx')
        
        Returns:
            Dictionary containing optimized model and performance metrics
        """

        logging.info(f"Starting {optimization_type} optimization...")
        
        start_time = time.time()
        
        if optimization_type == "torchscript":
            optimized_model = self._optimize_with_torchscript(model, example_input)
        elif optimization_type == "quantization":
            optimized_model = self._optimize_with_quantization(model)
        elif optimization_type == "onnx":
            optimized_model = self._optimize_with_onnx(model, example_input)
        else:
            raise ValueError(f"Unsupported optimization type: {optimization_type}")
        
        optimization_time = time.time() - start_time
        
        # Benchmark performance
        performance_metrics = self._benchmark_model(model, optimized_model, example_input)
        
        result = {
            'optimized_model': optimized_model,
            'optimization_time': optimization_time,
            'performance_metrics': performance_metrics,
            'optimization_type': optimization_type
        }
        
        logging.info(f"Optimization completed in {optimization_time:.2f} seconds")
        return result
    
    def _optimize_with_torchscript(self, model: nn.Module, example_input: torch.Tensor):
        """Optimize model using TorchScript tracing."""

        model.eval()
        with torch.no_grad():
            traced_model = torch.jit.trace(model, example_input)
            traced_model = torch.jit.optimize_for_inference(traced_model)
        return traced_model
    
    def _optimize_with_quantization(self, model: nn.Module):
        """Optimize model using dynamic quantization."""

        quantized_model = quantize_dynamic(
            model, 
            {nn.Linear, nn.Conv2d}, 
            dtype=torch.qint8
        )
        return quantized_model
    
    def _optimize_with_onnx(self, model: nn.Module, example_input: torch.Tensor):
        """Optimize model by converting to ONNX format."""

        model.eval()
        
        # Export to ONNX
        onnx_path = "/tmp/model.onnx"
        torch.onnx.export(
            model,
            example_input,
            onnx_path,
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        
        # Create ONNX Runtime session
        ort_session = ort.InferenceSession(onnx_path)
        return ort_session
    
    def _benchmark_model(self, original_model: nn.Module, optimized_model, 
                        example_input: torch.Tensor, num_runs: int = 100) -> Dict[str, float]:
        """Benchmark original vs optimized model performance."""
        
        # Benchmark original model
        original_times = []
        original_model.eval()
        
        with torch.no_grad():
            # Warmup
            for _ in range(10):
                _ = original_model(example_input)
            
            # Actual benchmark
            for _ in range(num_runs):
                start_time = time.time()
                _ = original_model(example_input)
                original_times.append(time.time() - start_time)
        
        # Benchmark optimized model
        optimized_times = []
        
        if isinstance(optimized_model, torch.jit.ScriptModule):
            # TorchScript model
            with torch.no_grad():
                # Warmup
                for _ in range(10):
                    _ = optimized_model(example_input)
                
                # Actual benchmark
                for _ in range(num_runs):
                    start_time = time.time()
                    _ = optimized_model(example_input)
                    optimized_times.append(time.time() - start_time)
                    
        elif isinstance(optimized_model, ort.InferenceSession):
            # ONNX model
            input_name = optimized_model.get_inputs()[0].name
            input_data = {input_name: example_input.numpy()}
            
            # Warmup
            for _ in range(10):
                _ = optimized_model.run(None, input_data)
            
            # Actual benchmark
            for _ in range(num_runs):
                start_time = time.time()
                _ = optimized_model.run(None, input_data)
                optimized_times.append(time.time() - start_time)
        else:
            # Quantized PyTorch model
            with torch.no_grad():
                # Warmup
                for _ in range(10):
                    _ = optimized_model(example_input)
                
                # Actual benchmark
                for _ in range(num_runs):
                    start_time = time.time()
                    _ = optimized_model(example_input)
                    optimized_times.append(time.time() - start_time)
        
        original_avg = np.mean(original_times) * 1000  # Convert to ms
        optimized_avg = np.mean(optimized_times) * 1000  # Convert to ms
        speedup = original_avg / optimized_avg
        
        return {
            'original_latency_ms': original_avg,
            'optimized_latency_ms': optimized_avg,
            'speedup_factor': speedup,
            'latency_reduction_percent': ((original_avg - optimized_avg) / original_avg) * 100
        }
    
    def batch_inference(self, model, inputs: List[torch.Tensor], batch_size: int = 32) -> List[torch.Tensor]:
        """

        Perform batched inference for improved throughput.
        
        Args:
            model: Optimized model for inference
            inputs: List of input tensors
            batch_size: Batch size for processing
        
        Returns:
            List of output tensors
        """
        logging.info(f"Starting batched inference with batch size {batch_size}")
        
        results = []
        model.eval()
        
        with torch.no_grad():
            for i in range(0, len(inputs), batch_size):
                batch_inputs = inputs[i:i + batch_size]
                
                # Stack inputs into a batch
                if len(batch_inputs) > 1:
                    batch_tensor = torch.stack(batch_inputs)
                else:
                    batch_tensor = batch_inputs[0].unsqueeze(0)
                
                # Perform inference
                if isinstance(model, torch.jit.ScriptModule):
                    batch_outputs = model(batch_tensor)
                elif isinstance(model, ort.InferenceSession):
                    input_name = model.get_inputs()[0].name
                    input_data = {input_name: batch_tensor.numpy()}
                    batch_outputs = model.run(None, input_data)[0]
                    batch_outputs = torch.from_numpy(batch_outputs)
                else:
                    batch_outputs = model(batch_tensor)
                
                # Split batch outputs back to individual results
                for j in range(batch_outputs.shape[0]):
                    results.append(batch_outputs[j])
        
        logging.info(f"Batched inference completed for {len(inputs)} samples")
        return results
    
    def cache_predictions(self, model, inputs: List[torch.Tensor], 
                         cache_file: str = "/tmp/prediction_cache.pkl") -> Dict[str, torch.Tensor]:
        """
        Cache predictions to avoid recomputation for repeated inputs.
        
        Args:
            model: Model for inference
            inputs: List of input tensors
            cache_file: File path for caching predictions
        
        Returns:
            Dictionary mapping input hashes to predictions
        """

        logging.info("Starting prediction caching...")
        
        try:
            # Load existing cache
            with open(cache_file, 'rb') as f:
                cache = RestrictedUnpickler(f).load()
        except FileNotFoundError:
            cache = {}
        
        new_predictions = 0
        
        for input_tensor in inputs:
            # Create hash of input tensor
            input_hash = hash(input_tensor.data.tobytes())
            
            if input_hash not in cache:
                # Compute prediction
                model.eval()
                with torch.no_grad():
                    if isinstance(model, ort.InferenceSession):
                        input_name = model.get_inputs()[0].name
                        input_data = {input_name: input_tensor.unsqueeze(0).numpy()}
                        prediction = model.run(None, input_data)[0]
                        prediction = torch.from_numpy(prediction).squeeze(0)
                    else:
                        prediction = model(input_tensor.unsqueeze(0)).squeeze(0)
                
                cache[input_hash] = prediction
                new_predictions += 1
        
        # Save updated cache
        with open(cache_file, 'wb') as f:
            pickle.dump(cache, f)
        
        logging.info(f"Caching completed. {new_predictions} new predictions cached.")
        return cache
    
    def profile_model_performance(self, model, example_input: torch.Tensor) -> Dict[str, Any]:
        """
        Profile model performance including memory usage and FLOPs.
        
        Args:
            model: Model to profile
            example_input: Example input tensor
        
        Returns:
            Dictionary containing profiling results
        """

        logging.info("Starting model profiling...")
        
        # Memory profiling
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        model.eval()
        with torch.no_grad():
            # Measure inference time
            start_time = time.time()
            output = model(example_input)
            inference_time = time.time() - start_time
            
            # Measure model size
            model_size = sum(p.numel() * p.element_size() for p in model.parameters())
            
            # Count parameters
            total_params = sum(p.numel() for p in model.parameters())
            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        profile_results = {
            'inference_time_ms': inference_time * 1000,
            'model_size_mb': model_size / (1024 * 1024),
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'output_shape': list(output.shape),
            'input_shape': list(example_input.shape)
        }
        
        logging.info("Model profiling completed")
        return profile_results

# --- Example Usage ---
if __name__ == "__main__":
    logging.info("--- Inference Optimization Example ---")
    
    # Create a simple model for demonstration
    class SimpleModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(100, 50)
            self.fc2 = nn.Linear(50, 25)
            self.fc3 = nn.Linear(25, 2)
            self.relu = nn.ReLU()
        
        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.relu(self.fc2(x))
            x = self.fc3(x)
            return x
    
    # Initialize optimizer and model
    optimizer = InferenceOptimizer()
    model = SimpleModel()
    example_input = torch.randn(1, 100)
    
    # Test different optimization techniques
    for opt_type in ["torchscript", "quantization"]:
        logging.info(f"\n--- Testing {opt_type} optimization ---")
        result = optimizer.optimize_pytorch_model(model, example_input, opt_type)
        
        metrics = result['performance_metrics']
        logging.info(f"Original latency: {metrics['original_latency_ms']:.2f} ms")
        logging.info(f"Optimized latency: {metrics['optimized_latency_ms']:.2f} ms")
        logging.info(f"Speedup: {metrics['speedup_factor']:.2f}x")
        logging.info(f"Latency reduction: {metrics['latency_reduction_percent']:.1f}%")
    
    # Test batch inference
    logging.info("\n--- Testing batch inference ---")
    test_inputs = [torch.randn(100) for _ in range(50)]
    batch_results = optimizer.batch_inference(model, test_inputs, batch_size=8)
    logging.info(f"Processed {len(batch_results)} samples in batches")
    
    # Test model profiling
    logging.info("\n--- Testing model profiling ---")
    profile_results = optimizer.profile_model_performance(model, example_input)
    for key, value in profile_results.items():
        logging.info(f"{key}: {value}")
    
    logging.info("\nInference optimization example completed!")
