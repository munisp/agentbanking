FROM python:3.12-slim-bookworm-slim

WORKDIR /app

RUN pip install flask flask-cors

COPY src/ ./src/

EXPOSE 5433

RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD ["python", "src/metadata_service.py"]
