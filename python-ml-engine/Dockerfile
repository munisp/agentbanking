FROM python:3.11-slim
WORKDIR /app
COPY app.py ./
COPY test_app.py ./
ENV PYTHON_ML_PORT=9300
EXPOSE 9300
HEALTHCHECK --interval=15s --timeout=5s CMD curl -f http://localhost:9300/health || exit 1
CMD ["python3", "app.py"]
