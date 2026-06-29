FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 9010
CMD ["gunicorn", "-b", "0.0.0.0:9010", "main:create_app()"]
