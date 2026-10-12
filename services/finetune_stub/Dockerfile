FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY finetune_server.py .
CMD ["uvicorn", "finetune_server:app", "--host", "0.0.0.0", "--port", "9040"]
