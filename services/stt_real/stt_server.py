import os
import tempfile
import threading
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
import whisper

MODEL_NAME = os.getenv("WHISPER_MODEL", "base")

app = FastAPI(title="STT Server")
model_lock = threading.Lock()
model: Optional[Any] = None
model_load_error: Optional[str] = None


def get_model():
    global model
    global model_load_error

    if model is not None:
        return model

    with model_lock:
        if model is not None:
            return model

        try:
            model = whisper.load_model(MODEL_NAME)
            model_load_error = None
        except Exception as exc:
            model_load_error = str(exc)
            raise HTTPException(
                status_code=500,
                detail=f"Could not load whisper model '{MODEL_NAME}': {exc}",
            ) from exc

    return model


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "loaded": model is not None,
        "load_error": model_load_error,
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    provider: str = Form("whisper"),
    language: str = Form("ko"),
    task: str = Form("transcribe"),
    temperature: float = Form(0.0),
    return_timestamps: str = Form("true"),
):
    if provider == "stub":
        return {
            "text": f"[stub] recognized text from {file.filename}",
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": f"[stub] {file.filename}",
                }
            ],
            "language": "ko" if language == "auto" else language,
        }

    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        kwargs = {
            "task": task,
            "temperature": temperature,
        }
        if language != "auto":
            kwargs["language"] = language

        stt_model = get_model()
        result = stt_model.transcribe(temp_path, **kwargs)

        segments = []
        if str(return_timestamps).lower() == "true":
            for seg in result.get("segments", []) or []:
                segments.append(
                    {
                        "start": seg.get("start", 0.0),
                        "end": seg.get("end", 0.0),
                        "text": (seg.get("text", "") or "").strip(),
                    }
                )

        return {
            "text": (result.get("text", "") or "").strip(),
            "segments": segments,
            "language": result.get("language", language),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {e}") from e

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
