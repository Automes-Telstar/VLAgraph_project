from __future__ import annotations

import base64
import os
import tempfile
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from TTS.api import TTS

TTS_MODEL = os.getenv("TTS_MODEL", "tts_models/ko/ct2/tts_transformer")
app = FastAPI(title="TTS Real Server")
model_lock = threading.Lock()
model: Optional[TTS] = None
model_load_error: Optional[str] = None


def get_model() -> TTS:
    global model
    global model_load_error

    if model is not None:
        return model

    with model_lock:
        if model is not None:
            return model

        try:
            model = TTS(TTS_MODEL, progress_bar=False, gpu=False)
            model_load_error = None
        except Exception as exc:
            model_load_error = str(exc)
            raise HTTPException(
                status_code=500,
                detail=f"Could not load TTS model '{TTS_MODEL}': {exc}",
            ) from exc

    return model


class TTSRequest(BaseModel):
    text: str
    provider: str = "tts"
    language: str = "ko"
    voice: str = "default"


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": TTS_MODEL,
        "loaded": model is not None,
        "load_error": model_load_error,
    }


@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    tts_model = get_model()
    temp_path: Optional[str] = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_path = tmp.name
            try:
                tts_model.tts_to_file(
                    text=request.text,
                    speaker=request.voice if request.voice != "default" else None,
                    language=request.language if request.language else None,
                    file_path=temp_path,
                )
            except TypeError:
                tts_model.tts_to_file(text=request.text, file_path=temp_path)

        with open(temp_path, "rb") as f:
            audio_data = f.read()

        return {"audio": base64.b64encode(audio_data).decode("utf-8")}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
