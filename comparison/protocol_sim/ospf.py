from __future__ import annotations

from math import log2

from .protocols import (
    PhaseBreakdown,
    ProtocolResult,
    _affected_edges,
    _choose_focus_edge,
    _connected_component,
    _graph_metrics,
)
from .topology import Topology


def simulate_ospf(topology: Topology) -> ProtocolResult:
    node_count, edge_count, avg_delay, avg_weight, diameter = _graph_metrics(topology)
    focus_edge = _choose_focus_edge(topology)
    impacted_nodes = {focus_edge.source, focus_edge.target}
    affected_nodes = _connected_component(topology, impacted_nodes)

    detection = max(0.7, avg_delay * 0.8)
    flooding = diameter * avg_delay * 1.9 + edge_count * 0.18
    recomputation = node_count * (0.55 + log2(node_count + 1) * 0.22 + avg_weight * 0.03)
    stabilization = max(0.5, avg_delay * 0.9 + diameter * 0.25)

    messages = int(edge_count * node_count * 1.6)
    notes = [
        "OSPF floods the change to every router in the domain.",
        "Every router runs SPF again, so the work scales with the full topology.",
    ]
    return ProtocolResult(
        name="OSPF-like baseline",
        phases=PhaseBreakdown(detection, flooding, recomputation, stabilization),
        messages=messages,
        affected_nodes=node_count,
        affected_edges=edge_count,
        scope="Global flooding across the full routing domain",
        notes=notes,
    )
