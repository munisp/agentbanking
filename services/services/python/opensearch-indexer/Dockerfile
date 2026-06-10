FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV OPENSEARCH_URL=http://opensearch:9200
ENV PORT=8092
EXPOSE 8092
CMD ["python", "main.py"]
