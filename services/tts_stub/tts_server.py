from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import io
from gtts import gTTS

app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    provider: str = "gtts"
    language: str = "ko"
    voice: str = "default"

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    try:
        tts = gTTS(text=request.text, lang=request.language, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_data = audio_buffer.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        return {"audio": audio_base64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))