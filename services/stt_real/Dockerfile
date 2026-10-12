FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1+cpu && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY stt_server.py /app/stt_server.py

EXPOSE 9090

CMD ["uvicorn", "stt_server:app", "--host", "0.0.0.0", "--port", "9090"]
