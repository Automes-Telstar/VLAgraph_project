from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


DEFAULT_MODEL_PATH = Path("/models/GR00T-N1.7-3B")
DEFAULT_BACKBONE_PATH = Path("/models/Cosmos-Reason2-2B")
PREPARED_MODEL_PATH = Path(os.getenv("GR00T_PREPARED_MODEL_PATH", "/tmp/vlagraph_gr00t_model"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _replace_cosmos_ref(value: Any, backbone_path: str) -> Any:
    if isinstance(value, str) and value == "nvidia/Cosmos-Reason2-2B":
        return backbone_path
    if isinstance(value, dict):
        return {key: _replace_cosmos_ref(item, backbone_path) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_cosmos_ref(item, backbone_path) for item in value]
    return value


def _prepare_overlay(model_path: Path, backbone_path: Path) -> Path:
    if not model_path.exists():
        raise FileNotFoundError(f"GR00T model path does not exist: {model_path}")
    if not backbone_path.exists():
        raise FileNotFoundError(f"Cosmos backbone path does not exist: {backbone_path}")

    if PREPARED_MODEL_PATH.exists() or PREPARED_MODEL_PATH.is_symlink():
        if PREPARED_MODEL_PATH.is_dir() and not PREPARED_MODEL_PATH.is_symlink():
            shutil.rmtree(PREPARED_MODEL_PATH)
        else:
            PREPARED_MODEL_PATH.unlink()
    PREPARED_MODEL_PATH.mkdir(parents=True, exist_ok=True)

    for entry in model_path.iterdir():
        target = PREPARED_MODEL_PATH / entry.name
        if entry.name in {"config.json", "processor_config.json"}:
            continue
        try:
            target.symlink_to(entry, target_is_directory=entry.is_dir())
        except OSError:
            if entry.is_dir():
                shutil.copytree(entry, target)
            else:
                shutil.copy2(entry, target)

    backbone = str(backbone_path)

    config_path = model_path / "config.json"
    with config_path.open("r", encoding="utf-8") as fh:
        config = _replace_cosmos_ref(json.load(fh), backbone)
    if isinstance(config, dict):
        config["model_name"] = backbone
    with (PREPARED_MODEL_PATH / "config.json").open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)

    processor_path = model_path / "processor_config.json"
    with processor_path.open("r", encoding="utf-8") as fh:
        processor = _replace_cosmos_ref(json.load(fh), backbone)
    if isinstance(processor, dict):
        kwargs = processor.setdefault("processor_kwargs", {})
        if isinstance(kwargs, dict):
            kwargs["model_name"] = backbone
    with (PREPARED_MODEL_PATH / "processor_config.json").open("w", encoding="utf-8") as fh:
        json.dump(processor, fh, ensure_ascii=False, indent=2)

    return PREPARED_MODEL_PATH


def _patch_local_backbone_acceptance() -> None:
    import gr00t.model.gr00t_n1d7.gr00t_n1d7 as gr00t_n1d7

    original = gr00t_n1d7.get_backbone_cls

    def patched(config):
        model_name = str(getattr(config, "model_name", "") or "")
        if os.path.isdir(model_name):
            from gr00t.model.modules.qwen3_backbone import Qwen3Backbone

            return Qwen3Backbone
        return original(config)

    gr00t_n1d7.get_backbone_cls = patched


def main() -> None:
    os.environ.setdefault("GROOT_PATCH_MISTRAL", "1")
    os.environ.setdefault("GROOT_HF_LOCAL_FIRST", "1")

    model_path = Path(os.getenv("GR00T_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
    backbone_path = Path(os.getenv("GR00T_BACKBONE_MODEL_PATH", str(DEFAULT_BACKBONE_PATH)))
    embodiment_tag = os.getenv("GR00T_EMBODIMENT_TAG", "REAL_G1")
    device = os.getenv("GR00T_DEVICE", "cuda")
    host = os.getenv("GR00T_POLICY_HOST", "0.0.0.0")
    port = int(os.getenv("GR00T_POLICY_PORT", "5555"))
    strict = _env_bool("GR00T_POLICY_STRICT", True)

    prepared_model = _prepare_overlay(model_path, backbone_path)
    _patch_local_backbone_acceptance()

    from gr00t.data.embodiment_tags import EmbodimentTag
    from gr00t.policy.gr00t_policy import Gr00tPolicy
    from gr00t.policy.server_client import PolicyServer

    resolved_tag = EmbodimentTag.resolve(embodiment_tag)
    print("Starting VLA Graph GR00T policy server", flush=True)
    print(f"  model: {prepared_model}", flush=True)
    print(f"  backbone: {backbone_path}", flush=True)
    print(f"  embodiment: {resolved_tag}", flush=True)
    print(f"  device: {device}", flush=True)
    print(f"  bind: {host}:{port}", flush=True)

    policy = Gr00tPolicy(
        embodiment_tag=resolved_tag,
        model_path=str(prepared_model),
        device=device,
        strict=strict,
    )
    server = PolicyServer(policy=policy, host=host, port=port)
    server.run()


if __name__ == "__main__":
    main()
