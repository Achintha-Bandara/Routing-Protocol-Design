from __future__ import annotations

from dataclasses import dataclass
from math import log2
from collections import deque
import heapq
import math
from pathlib import Path
from typing import Any

from .topology import Edge, Topology, load_topology


@dataclass(frozen=True)
class PhaseBreakdown:
    detection: float
    flooding: float
    recomputation: float
    stabilization: float

    @property
    def total(self) -> float:
        return self.detection + self.flooding + self.recomputation + self.stabilization


@dataclass(frozen=True)
class ProtocolResult:
    name: str
    phases: PhaseBreakdown
    messages: int
    affected_nodes: int
    affected_edges: int
    scope: str
    notes: list[str]

    @property
    def total_time(self) -> float:
        return self.phases.total


@dataclass(frozen=True)
class RoutingMetricProfile:
    latency_weight: float = 0.50  # used as w1 in composite formula
    bandwidth_weight: float = 0.25  # used as w2 in composite formula
    reliability_weight: float = 0.18
    load_weight: float = 0.07


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _adaptive_edge_cost(
    edge: Edge, topology: Topology | None = None, profile: RoutingMetricProfile | None = None
) -> float:
    profile = profile or RoutingMetricProfile()
    # Composite cost using the attachment formula plus small terms for
    # reliability and load to preserve existing behavior.
    if topology is not None and topology.edges:
        L_max = max(max(0.0001, e.delay) for e in topology.edges)
        BW_max = max(max(0.0001, e.bandwidth) for e in topology.edges)
    else:
        L_max = max(0.0001, edge.delay)
        BW_max = max(0.0001, edge.bandwidth)

    latency_norm = edge.delay / L_max
    bw_ratio = max(1e-6, min(1.0, edge.bandwidth / BW_max))
    bandwidth_term = -math.log(bw_ratio)

    composite = profile.latency_weight * latency_norm + profile.bandwidth_weight * bandwidth_term
    reliability_term = 1.0 - _clamp(edge.reliability, 0.0, 1.0)
    load_term = max(0.0, edge.weight / 10.0)
    return composite + profile.reliability_weight * reliability_term + profile.load_weight * load_term


def _metric_graph(topology: Topology, profile: RoutingMetricProfile | None = None) -> dict[str, list[tuple[str, float, Edge]]]:
    graph: dict[str, list[tuple[str, float, Edge]]] = {node: [] for node in topology.nodes}
    for edge in topology.edges:
        cost = _adaptive_edge_cost(edge, topology=topology, profile=profile)
        graph.setdefault(edge.source, []).append((edge.target, cost, edge))
        graph.setdefault(edge.target, []).append((edge.source, cost, edge))
    return graph


def _multimetric_shortest_paths(
    topology: Topology,
    source: str,
    profile: RoutingMetricProfile | None = None,
) -> tuple[dict[str, float], dict[str, str | None]]:
    graph = _metric_graph(topology, profile)
    dist: dict[str, float] = {node: float("inf") for node in topology.nodes}
    prev: dict[str, str | None] = {node: None for node in topology.nodes}
    dist[source] = 0.0
    queue: list[tuple[float, str]] = [(0.0, source)]

    while queue:
        current_dist, node = heapq.heappop(queue)
        if current_dist > dist[node]:
            continue
        for neighbor, edge_cost, _edge in graph.get(node, []):
            candidate = current_dist + edge_cost
            if candidate < dist[neighbor]:
                dist[neighbor] = candidate
                prev[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))
    return dist, prev


def build_adaptive_routing_table(
    topology: Topology,
    source: str,
    profile: RoutingMetricProfile | None = None,
    active_edges: set[tuple[str, str]] | None = None,
) -> list[tuple[str, str, float]]:
    if active_edges is None:
        dist, prev = _multimetric_shortest_paths(topology, source, profile)
    else:
        graph: dict[str, list[tuple[str, float, Edge]]] = {node: [] for node in topology.nodes}
        for edge in topology.edges:
            key = tuple(sorted((edge.source, edge.target)))
            if key not in active_edges:
                continue
            cost = _adaptive_edge_cost(edge, topology=topology, profile=profile)
            graph.setdefault(edge.source, []).append((edge.target, cost, edge))
            graph.setdefault(edge.target, []).append((edge.source, cost, edge))

        dist: dict[str, float] = {node: float("inf") for node in topology.nodes}
        prev: dict[str, str | None] = {node: None for node in topology.nodes}
        dist[source] = 0.0
        queue: list[tuple[float, str]] = [(0.0, source)]
        while queue:
            current_dist, node = heapq.heappop(queue)
            if current_dist > dist[node]:
                continue
            for neighbor, edge_cost, _edge in graph.get(node, []):
                candidate = current_dist + edge_cost
                if candidate < dist[neighbor]:
                    dist[neighbor] = candidate
                    prev[neighbor] = node
                    heapq.heappush(queue, (candidate, neighbor))

    table: list[tuple[str, str, float]] = []
    for dest in topology.nodes:
        if dest == source:
            continue
        if dist[dest] == float("inf"):
            table.append((dest, "-", float("inf")))
            continue
        hop = dest
        while prev[hop] is not None and prev[hop] != source:
            hop = prev[hop]  # type: ignore[assignment]
        next_hop = hop if prev[hop] is not None else dest if prev[dest] == source else hop
        table.append((dest, next_hop, dist[dest]))
    return table


def describe_new_protocol_features() -> list[str]:
    return [
        "Multi-metric routing selects paths using latency, bandwidth, reliability, and legacy load cost.",
        "Rapid convergence uses link-state flooding plus triggered updates after topology changes.",
        "Scalability is targeted for moderate domains (around 50 routers) with a clear path to multi-area extension.",
        "Security by design authenticates control messages and rejects replay/spoof attempts before state changes.",
        "Simplicity is preserved by reusing Dijkstra-style shortest-path computation and a compact packet model.",
        "Mobile adaptability supports reactive route repair for wireless-like failures or intermittent links.",
    ]


def _edge_key(edge: Edge) -> tuple[str, str]:
    return tuple(sorted((edge.source, edge.target)))


def _build_index(topology: Topology) -> dict[tuple[str, str], Edge]:
    return {_edge_key(edge): edge for edge in topology.edges}


def _choose_focus_edge(topology: Topology) -> Edge:
    event = topology.event or {}
    if event.get("type") == "link_weight_change" and isinstance(event.get("edge"), (list, tuple)):
        edge_lookup = _build_index(topology)
        key = tuple(sorted((str(event["edge"][0]), str(event["edge"][1]))))
        if key in edge_lookup:
            return edge_lookup[key]
    return topology.edges[0]


def _neighbors(topology: Topology) -> dict[str, list[str]]:
    graph = topology.adjacency()
    return {node: [neighbor for neighbor, _ in neighbors] for node, neighbors in graph.items()}


def _connected_component(topology: Topology, start_nodes: set[str]) -> set[str]:
    graph = _neighbors(topology)
    seen = set(start_nodes)
    queue = deque(start_nodes)
    while queue:
        node = queue.popleft()
        for neighbor in graph.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def _distance_limited_nodes(topology: Topology, seeds: set[str], depth_limit: int) -> set[str]:
    graph = _neighbors(topology)
    seen = set(seeds)
    frontier = deque((seed, 0) for seed in seeds)
    while frontier:
        node, depth = frontier.popleft()
        if depth >= depth_limit:
            continue
        for neighbor in graph.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append((neighbor, depth + 1))
    return seen


def _graph_metrics(topology: Topology) -> tuple[int, int, float, float, int]:
    node_count = len(topology.nodes)
    edge_count = len(topology.edges)
    avg_delay = sum(edge.delay for edge in topology.edges) / edge_count
    avg_weight = sum(edge.weight for edge in topology.edges) / edge_count

    graph = topology.adjacency()

    def bfs_distances(source: str) -> dict[str, int]:
        distances = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor, _ in graph.get(node, []):
                if neighbor not in distances:
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)
        return distances

    diameter = 0
    for node in topology.nodes:
        distances = bfs_distances(node)
        if len(distances) != node_count:
            raise ValueError("Topology must be connected for a fair convergence comparison.")
        diameter = max(diameter, max(distances.values()))

    return node_count, edge_count, avg_delay, avg_weight, diameter


def _affected_edges(topology: Topology, affected_nodes: set[str]) -> int:
    affected = 0
    affected_nodes = set(affected_nodes)
    for edge in topology.edges:
        if edge.source in affected_nodes or edge.target in affected_nodes:
            affected += 1
    return affected


def compare_protocols(topology: Topology) -> dict[str, Any]:
    from .aospf import simulate_aospf, simulate_aospf_secure
    from .ospf import simulate_ospf
    ospf = simulate_ospf(topology)
    aospf = simulate_aospf(topology)
    aospf_secure = simulate_aospf_secure(topology)

    improvement = ((ospf.total_time - aospf.total_time) / ospf.total_time) * 100.0
    message_reduction = ((ospf.messages - aospf.messages) / ospf.messages) * 100.0
    improvement_secure = ((ospf.total_time - aospf_secure.total_time) / ospf.total_time) * 100.0
    message_reduction_secure = ((ospf.messages - aospf_secure.messages) / ospf.messages) * 100.0

    changed_aspects = [
        "Flooding scope is reduced from full-domain broadcast to a triggered, impacted neighborhood.",
        "SPF remains incremental, but route selection can now consider latency, bandwidth, and reliability.",
        "Authenticated control messages stop spoofing and replay before route state changes are accepted.",
        "Reactive repair can repair broken wireless-like paths without rebuilding the whole domain.",
        "Scalability stays practical for moderate networks because the recomputation scope is localized.",
    ]

    advantages = [
        "Faster convergence on the same topology.",
        "Lower control-plane message volume than full-domain flooding.",
        "Less CPU work on unaffected routers.",
        "Better path quality because the protocol can trade off latency, bandwidth, and reliability.",
        "Stronger security because control traffic is authenticated by design.",
    ]
    disadvantages = [
        "More complex state tracking than plain OSPF.",
        "Needs accurate locality detection to avoid missing impacted paths.",
        "May be harder to standardize and troubleshoot in mixed environments.",
        "Multi-metric scoring requires careful weight tuning to avoid unstable path preferences.",
        "Security checks and encryption add small extra processing overhead.",
    ]

    return {
        "topology": topology,
        "ospf": ospf,
        "aospf": aospf,
        "aospf_secure": aospf_secure,
        "fast": aospf,
        "fast_secure": aospf_secure,
        "improvement_percent": improvement,
        "message_reduction_percent": message_reduction,
        "improvement_secure_percent": improvement_secure,
        "message_reduction_secure_percent": message_reduction_secure,
        "changed_aspects": changed_aspects,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "feature_notes": describe_new_protocol_features(),
        "timeline": {
            ospf.name: _cumulative_timeline(ospf),
            aospf.name: _cumulative_timeline(aospf),
            aospf_secure.name: _cumulative_timeline(aospf_secure),
        },
    }


def _cumulative_timeline(result: ProtocolResult) -> list[float]:
    phases = [
        result.phases.detection,
        result.phases.flooding,
        result.phases.recomputation,
        result.phases.stabilization,
    ]
    running = 0.0
    timeline = []
    for phase in phases:
        running += phase
        timeline.append(round(running, 3))
    return timeline


def compare_topology_file(path: str | Path) -> dict[str, Any]:
    return compare_protocols(load_topology(path))


def format_report(result: dict[str, Any]) -> str:
    ospf: ProtocolResult = result["ospf"]
    aospf: ProtocolResult = result["aospf"]
    aospf_secure: ProtocolResult | None = result.get("aospf_secure")
    topology: Topology = result["topology"]

    lines = [
        f"Topology: {topology.name}",
        f"Nodes: {len(topology.nodes)} | Edges: {len(topology.edges)}",
        "",
        f"{ospf.name}: {ospf.total_time:.2f} time units, {ospf.messages} messages, scope = {ospf.scope}",
        f"{aospf.name}: {aospf.total_time:.2f} time units, {aospf.messages} messages, scope = {aospf.scope}",
    ]
    if aospf_secure is not None:
        lines.append(f"{aospf_secure.name}: {aospf_secure.total_time:.2f} time units, {aospf_secure.messages} messages, scope = {aospf_secure.scope}")

    lines.extend([
        f"Convergence improvement: {result['improvement_percent']:.1f}% faster than OSPF-like baseline",
        f"Message reduction: {result['message_reduction_percent']:.1f}% fewer messages",
    ])

    if aospf_secure is not None:
        lines.extend([
            f"Convergence improvement (secure): {result['improvement_secure_percent']:.1f}% faster than OSPF-like baseline",
            f"Message reduction (secure): {result['message_reduction_secure_percent']:.1f}% fewer messages",
        ])

    lines.append("")
    lines.append("New protocol features:")
    lines.extend(f"- {item}" for item in result.get("feature_notes", []))
    lines.append("")
    lines.append("Protocol changes:")
    lines.extend(f"- {item}" for item in result["changed_aspects"])
    lines.append("")
    lines.append("Advantages of the new protocol:")
    lines.extend(f"- {item}" for item in result["advantages"])
    lines.append("")
    lines.append("Disadvantages of the new protocol:")
    lines.extend(f"- {item}" for item in result["disadvantages"])
    return "\n".join(lines)


def default_topology_path() -> Path:
    return Path(__file__).resolve().parent.parent / "topology.json"
