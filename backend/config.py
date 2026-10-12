# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


ALLOW_ORIGINS = [
    s.strip()
    for s in os.getenv("ALLOW_ORIGINS", "http://localhost:9173").split(",")
    if s.strip()
]

ALLOW_CREDENTIALS = env_bool("ALLOW_CREDENTIALS", True)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", "10000"))

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_TEXT_BYTES = int(os.getenv("MAX_TEXT_BYTES", "200000"))
MAX_DATASET_ROWS = int(os.getenv("MAX_DATASET_ROWS", "2000"))

MOCK_MODE = env_bool("MOCK_MODE", False)

ROUTE_HF_TEXT = os.getenv("ROUTE_HF_TEXT", "http://localhost:9008")
ROUTE_RAG = os.getenv("ROUTE_RAG", "http://localhost:9010")
ROUTE_LORA = os.getenv("ROUTE_LORA", "http://localhost:9020")
ROUTE_FINETUNE = os.getenv("ROUTE_FINETUNE", "http://localhost:9040")

# VLA
ROUTE_VLA_STUB = os.getenv("ROUTE_VLA_STUB", "http://vla_stub:9060")
ROUTE_VLA_REAL = os.getenv("ROUTE_VLA_REAL", "http://openvla_real:9060")
ENABLE_REAL_VLA = env_bool("ENABLE_REAL_VLA", False)

# 기본 선택 라우트
ROUTE_VLA = (
    ROUTE_VLA_REAL if ENABLE_REAL_VLA else ROUTE_VLA_STUB
)

# NVIDIA Isaac GR00T
ROUTE_GR00T_STUB = os.getenv("ROUTE_GR00T_STUB", "http://gr00t_stub:9070")
ROUTE_GR00T_REAL = os.getenv("ROUTE_GR00T_REAL", "http://gr00t_policy_adapter:9072")
ENABLE_REAL_GR00T = env_bool("ENABLE_REAL_GR00T", False)
GR00T_FALLBACK_TO_STUB = env_bool("GR00T_FALLBACK_TO_STUB", False)

ROUTE_GR00T = (
    ROUTE_GR00T_REAL if ENABLE_REAL_GR00T else ROUTE_GR00T_STUB
)

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "180"))

# Model volume import/sync
MODEL_STORE_DIR = os.getenv("MODEL_STORE_DIR", "/models")
MODEL_IMPORT_ROOTS = [
    s.strip()
    for s in os.getenv(
        "MODEL_IMPORT_ROOTS",
        "/host_downloads,/tmp/openvla_uploads,/models",
    ).split(",")
    if s.strip()
]
MODEL_IMPORT_WINDOWS_DOWNLOADS = os.getenv(
    "MODEL_IMPORT_WINDOWS_DOWNLOADS",
    "C:/Users/0/Downloads",
)
MODEL_IMPORT_DOWNLOADS_MOUNT = os.getenv(
    "MODEL_IMPORT_DOWNLOADS_MOUNT",
    "/host_downloads",
)
