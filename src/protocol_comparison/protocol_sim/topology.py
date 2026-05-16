from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float = 1.0
    delay: float = 1.0
    bandwidth: float = 100.0
    reliability: float = 0.99


@dataclass(frozen=True)
class Topology:
    name: str
    nodes: list[str]
    edges: list[Edge]
    event: dict[str, Any] | None = None

    def adjacency(self) -> dict[str, list[tuple[str, Edge]]]:
        graph: dict[str, list[tuple[str, Edge]]] = {node: [] for node in self.nodes}
        for edge in self.edges:
            graph.setdefault(edge.source, []).append((edge.target, edge))
            graph.setdefault(edge.target, []).append((edge.source, edge))
        return graph


def _as_node_name(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        for key in ("id", "name", "label"):
            if key in node:
                return str(node[key])
    raise ValueError(f"Unsupported node format: {node!r}")


def _as_edge(edge: Any) -> Edge:
    if isinstance(edge, dict):
        source = edge.get("source") or edge.get("from") or edge.get("a")
        target = edge.get("target") or edge.get("to") or edge.get("b")
        if source is None or target is None:
            raise ValueError(f"Edge is missing endpoints: {edge!r}")
        bandwidth = float(edge.get("bandwidth", edge.get("capacity", 100.0)))
        reliability = float(edge.get("reliability", edge.get("quality", 0.99)))
        return Edge(
            source=str(source),
            target=str(target),
            weight=float(edge.get("weight", edge.get("cost", 1.0))),
            delay=float(edge.get("delay", edge.get("latency", 1.0))),
            bandwidth=bandwidth,
            reliability=reliability,
        )
    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
        return Edge(source=str(edge[0]), target=str(edge[1]))
    raise ValueError(f"Unsupported edge format: {edge!r}")


def load_topology(path: str | Path) -> Topology:
    topology_path = Path(path)
    data = json.loads(topology_path.read_text(encoding="utf-8"))
    nodes = [_as_node_name(node) for node in data.get("nodes", [])]
    edges = [_as_edge(edge) for edge in data.get("edges", [])]
    if not nodes:
        raise ValueError("Topology must define at least one node.")
    if not edges:
        raise ValueError("Topology must define at least one edge.")
    name = str(data.get("name", topology_path.stem))
    event = data.get("event") if isinstance(data.get("event"), dict) else None
    return Topology(name=name, nodes=nodes, edges=edges, event=event)
