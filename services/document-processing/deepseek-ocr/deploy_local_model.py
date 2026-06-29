"""
Local DeepSeek Model Deployment Script
Downloads and configures DeepSeek VLM for self-hosted deployment
"""

import os
import logging
import torch
from pathlib import Path
from typing import Optional
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalDeepSeekDeployment:
    """Deploy and manage local DeepSeek model"""
    
    def __init__(
        self,
        model_dir: str = "/opt/models/deepseek",
        model_name: str = "deepseek-ai/deepseek-vl-7b-chat",
        use_quantization: bool = True,
        device: str = "cuda"
    ):
        """
        Initialize local deployment
        
        Args:
            model_dir: Local directory to store model
            model_name: HuggingFace model identifier
            use_quantization: Use 8-bit quantization to reduce memory
            device: Device to use (cuda/cpu)
        """
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.use_quantization = use_quantization
        self.device = device
        
        # Create model directory
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local DeepSeek deployment initialized at {self.model_dir}")
    
    def download_model(self) -> bool:
        """
        Download DeepSeek model to local storage
        
        Returns:
            True if successful
        """
        try:
            from transformers import AutoModel, AutoTokenizer, AutoProcessor
            
            logger.info(f"Downloading DeepSeek model: {self.model_name}")
            logger.info("This may take 30-60 minutes depending on connection speed...")
            
            # Download model
            logger.info("Downloading model weights...")
            model = AutoModel.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                cache_dir=str(self.model_dir),
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                low_cpu_mem_usage=True
            )
            
            # Download tokenizer
            logger.info("Downloading tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                cache_dir=str(self.model_dir)
            )
            
            # Try to download processor
            try:
                logger.info("Downloading processor...")
                processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    cache_dir=str(self.model_dir)
                )
            except:
                logger.warning("Processor not available for this model")
            
            # Save configuration
            config = {
                "model_name": self.model_name,
                "model_dir": str(self.model_dir),
                "device": self.device,
                "quantization": self.use_quantization,
                "downloaded_at": str(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
            }
            
            config_path = self.model_dir / "deployment_config.json"
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"✅ Model downloaded successfully to {self.model_dir}")
            logger.info(f"Model size: ~14-28 GB")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            return False
    
    def verify_installation(self) -> bool:
        """
        Verify model is properly installed
        
        Returns:
            True if model is ready
        """
        try:
            from transformers import AutoModel, AutoTokenizer
            
            logger.info("Verifying model installation...")
            
            # Check if model files exist
            config_path = self.model_dir / "deployment_config.json"
            if not config_path.exists():
                logger.error("Deployment config not found")
                return False
            
            # Try to load model
            logger.info("Loading model for verification...")
            model = AutoModel.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                cache_dir=str(self.model_dir),
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                low_cpu_mem_usage=True
            )
            
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                cache_dir=str(self.model_dir)
            )
            
            logger.info("✅ Model verification successful")
            logger.info(f"Model loaded on: {self.device}")
            logger.info(f"GPU available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            
            return True
            
        except Exception as e:
            logger.error(f"Model verification failed: {e}")
            return False
    
    def get_model_info(self) -> dict:
        """Get information about deployed model"""
        
        config_path = self.model_dir / "deployment_config.json"
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            config = {}
        
        info = {
            "model_name": self.model_name,
            "model_dir": str(self.model_dir),
            "device": self.device,
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "deployment_config": config
        }
        
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        return info
    
    def create_service_config(self) -> str:
        """
        Create systemd service configuration for auto-start
        
        Returns:
            Service configuration content
        """
        service_config = f"""[Unit]
Description=DeepSeek OCR Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/COMPREHENSIVE_SUPER_PLATFORM/backend/document-processing/deepseek-ocr
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="MODEL_DIR={self.model_dir}"
Environment="MODEL_NAME={self.model_name}"
ExecStart=/usr/bin/python3 -m uvicorn deepseek_service:app --host 0.0.0.0 --port 8045
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        service_path = Path("/tmp/deepseek-ocr.service")
        with open(service_path, "w") as f:
            f.write(service_config)
        
        logger.info(f"Service configuration created at {service_path}")
        logger.info("To install: sudo cp /tmp/deepseek-ocr.service /etc/systemd/system/")
        logger.info("To enable: sudo systemctl enable deepseek-ocr")
        logger.info("To start: sudo systemctl start deepseek-ocr")
        
        return service_config
    
    def create_docker_config(self) -> str:
        """
        Create Docker configuration for containerized deployment
        
        Returns:
            Dockerfile content
        """
        dockerfile = f"""FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y \\
    python3.10 \\
    python3-pip \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Download model (optional - can mount volume instead)
# RUN python3 deploy_local_model.py --download

# Expose port
EXPOSE 8045

# Set environment variables
ENV MODEL_DIR={self.model_dir}
ENV MODEL_NAME={self.model_name}
ENV CUDA_VISIBLE_DEVICES=0

# Run service
CMD ["uvicorn", "deepseek_service:app", "--host", "0.0.0.0", "--port", "8045"]
"""
        
        dockerfile_path = Path("/tmp/Dockerfile.deepseek")
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile)
        
        # Create docker-compose
        docker_compose = f"""version: '3.8'

services:
  deepseek-ocr:
    build:
      context: .
      dockerfile: Dockerfile.deepseek
    ports:
      - "8045:8045"
    volumes:
      - {self.model_dir}:/opt/models/deepseek
    environment:
      - MODEL_DIR=/opt/models/deepseek
      - MODEL_NAME={self.model_name}
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
"""
        
        compose_path = Path("/tmp/docker-compose.deepseek.yml")
        with open(compose_path, "w") as f:
            f.write(docker_compose)
        
        logger.info(f"Docker configuration created at {dockerfile_path}")
        logger.info(f"Docker Compose created at {compose_path}")
        
        return dockerfile
    
    def create_kubernetes_config(self) -> str:
        """
        Create Kubernetes deployment configuration
        
        Returns:
            Kubernetes YAML content
        """
        k8s_config = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: deepseek-ocr
  labels:
    app: deepseek-ocr
spec:
  replicas: 2
  selector:
    matchLabels:
      app: deepseek-ocr
  template:
    metadata:
      labels:
        app: deepseek-ocr
    spec:
      containers:
      - name: deepseek-ocr
        image: your-registry/deepseek-ocr:latest
        ports:
        - containerPort: 8045
        env:
        - name: MODEL_DIR
          value: "/opt/models/deepseek"
        - name: MODEL_NAME
          value: "{self.model_name}"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        resources:
          requests:
            memory: "32Gi"
            cpu: "4"
            nvidia.com/gpu: 1
          limits:
            memory: "64Gi"
            cpu: "8"
            nvidia.com/gpu: 1
        volumeMounts:
        - name: model-storage
          mountPath: /opt/models/deepseek
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: deepseek-model-pvc
      nodeSelector:
        gpu: "true"
---
apiVersion: v1
kind: Service
metadata:
  name: deepseek-ocr-service
spec:
  selector:
    app: deepseek-ocr
  ports:
  - protocol: TCP
    port: 8045
    targetPort: 8045
  type: LoadBalancer
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deepseek-model-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: fast-ssd
"""
        
        k8s_path = Path("/tmp/deepseek-k8s.yaml")
        with open(k8s_path, "w") as f:
            f.write(k8s_config)
        
        logger.info(f"Kubernetes configuration created at {k8s_path}")
        
        return k8s_config


def main():
    """Main deployment function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy DeepSeek model locally")
    parser.add_argument("--download", action="store_true", help="Download model")
    parser.add_argument("--verify", action="store_true", help="Verify installation")
    parser.add_argument("--info", action="store_true", help="Show model info")
    parser.add_argument("--create-service", action="store_true", help="Create systemd service config")
    parser.add_argument("--create-docker", action="store_true", help="Create Docker config")
    parser.add_argument("--create-k8s", action="store_true", help="Create Kubernetes config")
    parser.add_argument("--model-dir", default="/opt/models/deepseek", help="Model directory")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="Device")
    
    args = parser.parse_args()
    
    # Initialize deployment
    deployment = LocalDeepSeekDeployment(
        model_dir=args.model_dir,
        device=args.device
    )
    
    if args.download:
        logger.info("Starting model download...")
        success = deployment.download_model()
        if success:
            logger.info("✅ Download complete!")
        else:
            logger.error("❌ Download failed")
            return 1
    
    if args.verify:
        logger.info("Verifying installation...")
        success = deployment.verify_installation()
        if success:
            logger.info("✅ Verification passed!")
        else:
            logger.error("❌ Verification failed")
            return 1
    
    if args.info:
        info = deployment.get_model_info()
        logger.info("Model Information:")
        for key, value in info.items():
            logger.info(f"  {key}: {value}")
    
    if args.create_service:
        deployment.create_service_config()
    
    if args.create_docker:
        deployment.create_docker_config()
    
    if args.create_k8s:
        deployment.create_kubernetes_config()
    
    return 0


if __name__ == "__main__":
    exit(main())
