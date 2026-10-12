# backend/routes/runs.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.runtime.runner import run_graph

router = APIRouter()


class GraphNode(BaseModel):
    id: str
    type: str
    position: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    type: Optional[str] = None
    animated: Optional[bool] = None
    style: Optional[Dict[str, Any]] = None


class RunGraphRequest(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    input: Dict[str, Any] = Field(default_factory=dict)


@router.post("/api/graph/run")
def run_graph_api(req: RunGraphRequest):
    graph = {
        "nodes": [n.model_dump() for n in req.nodes],
        "edges": [e.model_dump() for e in req.edges],
    }
    return run_graph(graph, req.input)