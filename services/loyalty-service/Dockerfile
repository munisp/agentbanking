# Dockerfile for 54agent Loyalty Service
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (matches Helm values.yaml targetPort)
EXPOSE 8000

# Run the service
CMD ["python", "main.py"]
