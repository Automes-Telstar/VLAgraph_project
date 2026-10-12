from __future__ import annotations
from typing import Any, Dict
import json
import os
import csv


def exec_dataset_upload(node: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    data = node.get("data", {})
    dataset_path = data.get("datasetPath", "")
    dataset_format = data.get("datasetFormat", "jsonl")
    name = data.get("label", "Dataset Upload")
    initial_settings_path = data.get("initialSettingsPath", "")
    initial_settings_format = data.get("initialSettingsFormat", dataset_format)

    result: Dict[str, Any] = {
        "dataset": {
            "path": dataset_path,
            "format": dataset_format,
            "name": name,
        },
        "dataset_path": dataset_path,
        "dataset_format": dataset_format,
        "name": name,
    }
    if initial_settings_path:
        initial_settings = {
            "path": initial_settings_path,
            "format": initial_settings_format,
            "name": data.get("initialSettingsLabel") or f"{name} initial settings",
        }
        result.update(
            {
                "initialSettings": initial_settings,
                "initial_settings": initial_settings,
                "initialSettingsPath": initial_settings_path,
                "initial_settings_path": initial_settings_path,
                "initialSettingsFormat": initial_settings_format,
                "initial_settings_format": initial_settings_format,
            }
        )
    return result



def exec_dataset_preview(node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    source_node_id = node.get("data", {}).get("sourceNodeId", "")
    dataset_path = context.get(source_node_id, {}).get("dataset_path", "")
    max_rows = int(node.get("data", {}).get("maxRows", 3))

    if not dataset_path or not os.path.exists(dataset_path):
        return {"rows": [], "count": 0, "warning": "dataset file not found"}

    rows = []
    if dataset_path.endswith(".jsonl"):
        with open(dataset_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_rows:
                    break
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    elif dataset_path.endswith(".csv"):
        with open(dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)
    else:
        rows.append({"path": dataset_path, "preview": "preview not implemented for this format"})

    return {"rows": rows, "count": len(rows), "dataset_path": dataset_path}
