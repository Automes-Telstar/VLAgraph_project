from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

ROUTE_STT = os.getenv("ROUTE_STT", "http://localhost:9090")
ROUTE_TTS_STUB = os.getenv("ROUTE_TTS_STUB", "http://tts_stub:9091")
ROUTE_TTS_REAL = os.getenv("ROUTE_TTS_REAL", "http://tts_real:9091")
REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "300"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


def _node_props(node: Dict[str, Any]) -> Dict[str, Any]:
    data = (node or {}).get("data") or {}
    if not isinstance(data, dict):
        return {}

    props = data.get("props")
    if isinstance(props, dict) and props:
        merged = dict(props)
        for key, value in data.items():
            if key != "props" and key not in merged:
                merged[key] = value
        return merged

    return data


def _pick_first(inputs: Dict[str, Any], *keys: str):
    if not isinstance(inputs, dict):
        return None

    for k in keys:
        if k in inputs and inputs[k] not in (None, ""):
            return inputs[k]
    return None


def _incoming_values(
    node_id: str,
    edges: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for edge in edges:
        if edge.get("target") != node_id:
            continue

        source_id = edge.get("source")
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")

        source_payload = context.get(source_id)
        if source_payload is None:
            continue

        value = source_payload
        if source_handle:
            if not isinstance(source_payload, dict):
                continue
            if source_handle not in source_payload:
                continue
            value = source_payload[source_handle]

        key = target_handle or source_handle or source_id
        if key:
            result[key] = value

    return result


def _resolve_file_id_path(file_id: str) -> Optional[str]:
    if not file_id:
        return None

    candidate = os.path.join(UPLOAD_DIR, file_id)
    if os.path.exists(candidate):
        return candidate

    return None


def _resolve_audio_path(audio_input: Any) -> Optional[str]:
    if audio_input is None:
        return None

    if isinstance(audio_input, str):
        stripped = audio_input.strip()
        if not stripped:
            return None

        if os.path.exists(stripped):
            return stripped

        by_id = _resolve_file_id_path(stripped)
        if by_id:
            return by_id

        return None

    if isinstance(audio_input, dict):
        for key in ("path", "file_path", "saved_path", "audioPath"):
            value = audio_input.get(key)
            if isinstance(value, str) and value.strip() and os.path.exists(value):
                return value

        file_id = audio_input.get("file_id") or audio_input.get("id")
        if isinstance(file_id, str):
            by_id = _resolve_file_id_path(file_id)
            if by_id:
                return by_id

    return None


def _to_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "off", "")
    return bool(value)


def exec_speech_to_text(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)
    inputs = _incoming_values(node["id"], edges, context)

    audio_input = _pick_first(inputs, "audio", "file", "path", "value")
    if audio_input in (None, ""):
        audio_input = _pick_first(
            props,
            "audioPath",
            "audio_path",
            "path",
            "file_path",
            "saved_path",
        )

    audio_path = _resolve_audio_path(audio_input)

    if not audio_path:
        raise ValueError("speech_to_text node requires a valid audio input")

    provider = props.get("provider", "whisper")
    language = props.get("language", "ko")
    task = props.get("task", "transcribe")
    try:
        temperature = float(props.get("temperature", 0))
    except (TypeError, ValueError):
        temperature = 0.0
    return_timestamps = _to_bool(props.get("returnTimestamps", True), default=True)

    with open(audio_path, "rb") as f:
        files = {
            "file": (os.path.basename(audio_path), f, "application/octet-stream")
        }
        data = {
            "provider": str(provider),
            "language": str(language),
            "task": str(task),
            "temperature": str(temperature),
            "return_timestamps": "true" if return_timestamps else "false",
        }

        res = requests.post(
            f"{ROUTE_STT}/transcribe",
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT_SEC,
        )
        res.raise_for_status()
        result = res.json()

    text = result.get("text", "") or ""
    segments = result.get("segments", []) or []
    detected_language = result.get("language", "") or ""

    return {
        "text": text,
        "segments": segments,
        "language": detected_language,
        "audio_path": audio_path,
        "exec": True,
    }


def exec_text_to_speech(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)
    inputs = _incoming_values(node["id"], edges, context)

    text_input = _pick_first(inputs, "text", "value")
    if text_input in (None, ""):
        text_input = _pick_first(props, "text")

    if not text_input or not isinstance(text_input, str) or not text_input.strip():
        raise ValueError("text_to_speech node requires a valid text input")

    provider = props.get("provider", "tts")
    language = props.get("language", "ko")
    voice = props.get("voice", "default")

    # Select TTS service based on provider
    if provider.lower() == "stub":
        tts_url = ROUTE_TTS_STUB
    elif provider.lower() == "real":
        tts_url = ROUTE_TTS_REAL
    else:
        tts_url = ROUTE_TTS_STUB  # default to stub

    data = {
        "text": str(text_input),
        "provider": str(provider),
        "language": str(language),
        "voice": str(voice),
    }

    res = requests.post(
        f"{tts_url}/synthesize",
        json=data,
        timeout=REQUEST_TIMEOUT_SEC,
    )
    res.raise_for_status()
    result = res.json()

    audio_data = result.get("audio")
    if not audio_data:
        raise ValueError("TTS service did not return audio data")

    # Save audio to file
    import uuid
    import base64
    audio_filename = f"{uuid.uuid4()}.wav"
    audio_path = os.path.join(UPLOAD_DIR, audio_filename)
    with open(audio_path, "wb") as f:
        if isinstance(audio_data, str):
            f.write(base64.b64decode(audio_data))
        else:
            f.write(bytes(audio_data))

    return {
        "audio_path": audio_path,
        "text": text_input,
        "exec": True,
    }
