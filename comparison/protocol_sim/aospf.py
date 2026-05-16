from __future__ import annotations

from math import log2

from .protocols import (
    PhaseBreakdown,
    ProtocolResult,
    RoutingMetricProfile,
    _adaptive_edge_cost,
    _affected_edges,
    _choose_focus_edge,
    _distance_limited_nodes,
    _graph_metrics,
)
from .topology import Topology


def simulate_aospf(topology: Topology) -> ProtocolResult:
    node_count, edge_count, avg_delay, avg_weight, diameter = _graph_metrics(topology)
    focus_edge = _choose_focus_edge(topology)
    seeds = {focus_edge.source, focus_edge.target}
    adaptive_depth = 2 if node_count <= 50 else 3
    affected_nodes = _distance_limited_nodes(topology, seeds, depth_limit=adaptive_depth)
    if len(affected_nodes) < 2:
        affected_nodes = seeds
    affected_edge_count = _affected_edges(topology, affected_nodes)

    local_density = affected_edge_count / max(1, len(affected_nodes))
    profile = RoutingMetricProfile()
    adaptive_costs = [_adaptive_edge_cost(edge, topology=topology, profile=profile) for edge in topology.edges]
    avg_adaptive_cost = sum(adaptive_costs) / max(1, len(adaptive_costs))

    detection = max(0.42, avg_delay * 0.48)
    flooding = max(avg_delay * 0.82, (len(affected_nodes) / node_count) * diameter * avg_delay * 1.0)
    recomputation = len(affected_nodes) * (
        0.28 + log2(len(affected_nodes) + 1) * 0.11 + local_density * 0.05 + avg_adaptive_cost * 0.30
    )
    stabilization = max(0.30, avg_delay * 0.38 + local_density * 0.06)

    reactive_repair = 0.0
    if len(affected_nodes) < node_count:
        reactive_repair = max(0.08, avg_delay * 0.12)
        stabilization += reactive_repair

    security_cost = 0.06 + (0.02 if node_count > 50 else 0.0)
    detection += security_cost
    messages = int(max(1, affected_edge_count * len(affected_nodes) * 0.90 + len(affected_nodes) * 0.15))
    notes = [
        "AOSPF uses multi-metric path selection with latency, bandwidth, reliability, and load factors.",
        "Triggered link-state flooding keeps convergence fast after topology changes.",
        "Control messages are authenticated and replay-protected before route state changes are accepted.",
        "Optional payload encryption can be added on trusted links without changing path selection.",
        "Key management supports pre-shared symmetric keys or per-link static keys for the project scope.",
        "Incremental SPF keeps recomputation local, and reactive repair can be enabled for wireless-like failures.",
        "The model is intended for moderate-sized domains and can be extended toward multi-area operation.",
        "Implementation remains simple by reusing Dijkstra-style shortest-path computation and compact packet handling.",
    ]
    return ProtocolResult(
        name="AOSPF - Adaptive OSPF",
        phases=PhaseBreakdown(detection, flooding, recomputation, stabilization),
        messages=messages,
        affected_nodes=len(affected_nodes),
        affected_edges=affected_edge_count,
        scope="Localized multi-metric flooding with incremental recomputation, triggered updates, and security controls",
        notes=notes,
    )


def simulate_aospf_secure(topology: Topology) -> ProtocolResult:
    base = simulate_aospf(topology)

    enc_detection = base.phases.detection + 0.08
    enc_flooding = base.phases.flooding * 1.06
    enc_recomputation = base.phases.recomputation * 1.04
    enc_stabilization = base.phases.stabilization + 0.04
    enc_messages = int(base.messages * 1.05)

    notes = base.notes + [
        "Secure mode: control messages are authenticated and encrypted.",
        "Adds small delay and CPU overhead for crypto operations and replay checks.",
        "Prevents simple spoofing, replay, and route hijacking when keys are valid.",
    ]

    return ProtocolResult(
        name="AOSPF-Sec (AOSPF secure)",
        phases=PhaseBreakdown(enc_detection, enc_flooding, enc_recomputation, enc_stabilization),
        messages=enc_messages,
        affected_nodes=base.affected_nodes,
        affected_edges=base.affected_edges,
        scope=base.scope + " (authenticated updates)",
        notes=notes,
    )
