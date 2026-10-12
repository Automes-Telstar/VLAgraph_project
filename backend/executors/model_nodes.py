from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

from backend.config import (
    MODEL_IMPORT_DOWNLOADS_MOUNT,
    MODEL_IMPORT_ROOTS,
    MODEL_IMPORT_WINDOWS_DOWNLOADS,
    MODEL_STORE_DIR,
)


_SAFE_TARGET_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _incoming_values(
    node_id: str,
    edges: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for edge in edges:
        if edge["target"] != node_id:
            continue

        source_id = edge["source"]
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")
        source_payload = context.get(source_id)
        if source_payload is None:
            continue

        value = source_payload
        if source_handle:
            if not isinstance(source_payload, dict) or source_handle not in source_payload:
                continue
            value = source_payload[source_handle]

        key = target_handle or source_handle or source_id
        result[key] = value

    return result


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().strip('"').strip("'")


def _split_required_files(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[\n,;]+", str(value or "config.json"))

    files: list[str] = []
    for item in raw_items:
        text = _normalize_text(item).replace("\\", "/")
        if not text:
            continue
        if text.startswith("/") or ".." in Path(text).parts:
            raise ValueError(f"Invalid required file path: {text}")
        files.append(text)
    return files or ["config.json"]


def _normalize_source_path(value: Any) -> Path:
    text = _normalize_text(value)
    if not text:
        raise ValueError("sourcePath is required.")

    normalized = text.replace("\\", "/")
    windows_root = _normalize_text(MODEL_IMPORT_WINDOWS_DOWNLOADS).replace("\\", "/").rstrip("/")
    downloads_mount = _normalize_text(MODEL_IMPORT_DOWNLOADS_MOUNT).replace("\\", "/").rstrip("/")

    if windows_root and downloads_mount and normalized.lower().startswith(windows_root.lower()):
        suffix = normalized[len(windows_root) :].lstrip("/")
        normalized = f"{downloads_mount}/{suffix}" if suffix else downloads_mount

    return Path(normalized)


def _resolve_existing_path(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Source path not found: {path}") from exc


def _resolve_root(path: str) -> Path:
    root = Path(path)
    try:
        return root.resolve(strict=True)
    except FileNotFoundError:
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve(strict=True)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_source_allowed(source: Path) -> Path:
    resolved = _resolve_existing_path(source)
    allowed_roots = [_resolve_root(root) for root in MODEL_IMPORT_ROOTS]
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise PermissionError(f"sourcePath must be inside one of: {roots}")
    if not resolved.is_dir():
        raise ValueError(f"sourcePath must be a model directory: {resolved}")
    return resolved


def _validate_target_name(value: Any) -> str:
    target_name = _normalize_text(value)
    if not target_name:
        raise ValueError("targetName is required.")
    if not _SAFE_TARGET_NAME.match(target_name):
        raise ValueError("targetName may only contain letters, numbers, dot, dash, and underscore.")
    if target_name in {".", ".."}:
        raise ValueError("targetName cannot be '.' or '..'.")
    return target_name


def _target_path(target_name: str) -> tuple[Path, Path]:
    store_root = _resolve_root(MODEL_STORE_DIR)
    target = (store_root / target_name).resolve(strict=False)
    if not _is_relative_to(target, store_root):
        raise PermissionError("targetName resolved outside MODEL_STORE_DIR.")
    return store_root, target


def _missing_required_files(model_dir: Path, required_files: list[str]) -> list[str]:
    missing: list[str] = []
    for relative in required_files:
        if not (model_dir / relative).exists():
            missing.append(relative)
    return missing


def _copy_model_dir(source: Path, target: Path, *, overwrite: bool) -> bool:
    if target.exists():
        if not overwrite:
            return False
    tmp = target.parent / f".{target.name}.tmp-{int(time.time())}"
    if tmp.exists():
        shutil.rmtree(tmp)

    try:
        shutil.copytree(source, tmp, symlinks=True)
        if target.exists():
            shutil.rmtree(target)
        os.replace(tmp, target)
        return True
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def exec_model_sync(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    inputs = _incoming_values(node["id"], edges, context)

    source_raw = inputs.get("sourcePath", data.get("sourcePath", ""))
    target_raw = data.get("targetName", "")
    overwrite = bool(data.get("overwrite", False))
    required_files = _split_required_files(data.get("requiredFiles", "config.json"))

    source = _validate_source_allowed(_normalize_source_path(source_raw))
    target_name = _validate_target_name(target_raw)
    store_root, target = _target_path(target_name)

    copied = _copy_model_dir(source, target, overwrite=overwrite)
    missing = _missing_required_files(target, required_files)
    verified = not missing

    if missing:
        return {
            "ok": False,
            "error": "Model sync completed, but required files are missing.",
            "missing_files": missing,
            "model": {
                "name": target_name,
                "path": str(target),
                "verified": False,
            },
            "status": {
                "source_path": str(source),
                "target_path": str(target),
                "copied": copied,
                "overwrite": overwrite,
                "store_root": str(store_root),
                "required_files": required_files,
            },
        }

    return {
        "ok": True,
        "model": {
            "name": target_name,
            "path": str(target),
            "verified": True,
        },
        "model_name": target_name,
        "model_path": str(target),
        "status": {
            "message": "model synced" if copied else "model already present",
            "source_path": str(source),
            "target_path": str(target),
            "copied": copied,
            "overwrite": overwrite,
            "store_root": str(store_root),
            "required_files": required_files,
        },
    }
