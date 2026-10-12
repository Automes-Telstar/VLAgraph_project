FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY scripts/realsense_d435i_bridge.py /app/scripts/realsense_d435i_bridge.py

EXPOSE 9000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "9000", "--reload"]
