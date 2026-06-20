FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY main.py /app/main.py
WORKDIR /app
EXPOSE 8302
USER nobody:nobody
CMD ["python", "main.py"]
