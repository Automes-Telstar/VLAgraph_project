FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir --retries 10 --timeout 120 -r /app/requirements.txt

COPY vla_server.py /app/vla_server.py

EXPOSE 9060

CMD ["uvicorn", "vla_server:app", "--host", "0.0.0.0", "--port", "9060"]