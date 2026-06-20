FROM python:3.11-slim
WORKDIR /app
COPY main.py .
EXPOSE 8252
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8252/health')" || exit 1
CMD ["python", "main.py"]
