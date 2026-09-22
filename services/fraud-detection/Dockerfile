FROM python:3.12-slim-bookworm-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8101

RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--workers", "2", "--bind", "0.0.0.0:8153", "main:app"]
