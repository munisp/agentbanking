FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ cmake libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create directories
RUN mkdir -p models/weights models/registry /data/lakehouse /data/ab_tests

# Train models on build (generates weights)
RUN python train_all_models.py --n-transactions 50000 --n-customers 5000 --n-agents 500 --skip-gnn

# Inference server
EXPOSE 8300
CMD ["uvicorn", "inference.serving:app", "--host", "0.0.0.0", "--port", "8300"]
