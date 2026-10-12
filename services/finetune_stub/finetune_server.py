from __future__ import annotations
from typing import Any, Dict
from uuid import uuid4
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="OPENVLA FineTune Stub", version="0.1.0")


class FineTuneStartRequest(BaseModel):
    dataset_path: str = ""
    base_model: str = "openvla/openvla-7b"
    output_name: str = "openvla-exp"
    epochs: int = 1
    batch_size: int = 2
    learning_rate: float = 1e-4
    lora_enabled: bool = True


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "finetune_stub"}


@app.post("/finetune/start")
def start(req: FineTuneStartRequest) -> Dict[str, Any]:
    job_id = uuid4().hex[:12]
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "dataset_path": req.dataset_path,
        "base_model": req.base_model,
        "output_name": req.output_name,
        "training_args": {
            "epochs": req.epochs,
            "batch_size": req.batch_size,
            "learning_rate": req.learning_rate,
            "lora_enabled": req.lora_enabled,
        },
        "checkpoint_path": f"/checkpoints/{req.output_name}-{job_id}",
        "note": "stub job only; replace with a real trainer later",
    }
