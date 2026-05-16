from __future__ import annotations

from math import cos, pi, sin
from collections import deque
import heapq
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .simulation import compare_topology_file, default_topology_path, format_report
from .protocols import build_adaptive_routing_table


class ComparisonApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Protocol Comparison: OSPF / AOSPF / BGP / IS-IS / RIP")
        self.geometry("1280x860")
        self.minsize(1100, 760)

        self.topology_path = tk.StringVar(value=str(default_topology_path()))
        self._comparison = None

        self._build_ui()
        self.run_comparison()

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")

        ttk.Label(header, text="Topology File").pack(side="left")
        entry = ttk.Entry(header, textvariable=self.topology_path, width=80)
        entry.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(header, text="Browse", command=self.choose_file).pack(side="left", padx=4)
        ttk.Button(header, text="Run Comparison", command=self.run_comparison).pack(side="left", padx=4)
        ttk.Button(header, text="Open OSPF Simulation", command=self.open_ospf_window).pack(side="left", padx=4)
        ttk.Button(header, text="Open AOSPF Simulation", command=self.open_aospf_window).pack(side="left", padx=4)
        # legacy protocol buttons removed (BGP / IS-IS / RIP)

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=12)

        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=3)
        body.add(right, weight=2)

        self.bar_canvas = tk.Canvas(left, bg="#0f172a", height=260, highlightthickness=0)
        self.bar_canvas.pack(fill="x", expand=False)

        self.timeline_canvas = tk.Canvas(left, bg="#111827", height=280, highlightthickness=0)
        self.timeline_canvas.pack(fill="x", expand=False, pady=(12, 0))

        ttk.Label(left, text="Topology View", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 6))
        self.topology_canvas = tk.Canvas(left, bg="#0b1220", height=300, highlightthickness=0)
        self.topology_canvas.pack(fill="both", expand=True)

        ttk.Label(right, text="Comparison Summary", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.metrics = ttk.Treeview(right, columns=("metric", "ospf", "fast"), show="headings", height=9)
        self.metrics.heading("metric", text="Metric")
        self.metrics.heading("ospf", text="OSPF-like")
        self.metrics.heading("fast", text="AOSPF")
        self.metrics.column("metric", width=180, anchor="w")
        self.metrics.column("ospf", width=110, anchor="center")
        self.metrics.column("fast", width=110, anchor="center")
        self.metrics.pack(fill="x", pady=(8, 12))

        ttk.Label(right, text="Protocol Changes, Advantages, and Trade-offs", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.report_text = tk.Text(right, wrap="word", height=24, bg="#f8fafc", relief="flat")
        self.report_text.pack(fill="both", expand=True, pady=(8, 0))

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose topology JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected:
            self.topology_path.set(selected)
            self.run_comparison()

    def open_ospf_window(self) -> None:
        self._open_sim_window(protocol_type="ospf")

    def open_aospf_window(self) -> None:
        self._open_sim_window(protocol_type="aospf")

    def open_falp_window(self) -> None:
        self.open_aospf_window()

    def _open_sim_window(self, protocol_type: str) -> None:
        assert self._comparison is not None
        topology = self._comparison["topology"]

        win = tk.Toplevel(self)
        display_protocol = "AOSPF" if protocol_type == "aospf" else protocol_type.upper()
        win.title(f"{display_protocol} Simulation")
        win.geometry("760x520")

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)

        # layout: top canvas, bottom controls, right-side info (routing tables + CLI log)
        top_pane = ttk.PanedWindow(frame, orient="horizontal")
        top_pane.pack(fill="both", expand=True)

        canvas_frame = ttk.Frame(top_pane)
        info_frame = ttk.Frame(top_pane, width=320)
        top_pane.add(canvas_frame, weight=3)
        top_pane.add(info_frame, weight=1)

        canvas = tk.Canvas(canvas_frame, bg="#071029", height=420, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(8, 0))

        edge_names = [f"{e.source}-{e.target}" for e in topology.edges]
        selected_edge = tk.StringVar(value=edge_names[0] if edge_names else "")

        ttk.Label(controls, text="Select edge:").pack(side="left")
        edge_combo = ttk.Combobox(controls, values=edge_names, textvariable=selected_edge, width=22)
        edge_combo.pack(side="left", padx=6)

        run_btn = ttk.Button(controls, text="Run Simulation")
        run_btn.pack(side="left", padx=6)
        disc_btn = ttk.Button(controls, text="Disconnect Link")
        disc_btn.pack(side="left", padx=6)
        restore_btn = ttk.Button(controls, text="Restore Links")
        restore_btn.pack(side="left", padx=6)

        # Build positions like main topology view
        width = max(canvas.winfo_width(), 700)
        height = int(canvas["height"])
        center_x = width / 2
        center_y = height / 2 + 10
        radius = min(width, height) * 0.34

        nodes = list(topology.nodes)
        positions: dict[str, tuple[float, float]] = {}
        for index, node in enumerate(nodes):
            angle = (2 * pi * index / max(1, len(nodes))) - pi / 2
            x = center_x + radius * cos(angle)
            y = center_y + radius * sin(angle)
            positions[node] = (x, y)

        active_edges = {tuple(sorted((e.source, e.target))) for e in topology.edges}

        # --- Info pane: routing tables and CLI log ---
        ttk.Label(info_frame, text="Routing Tables", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(6, 2), padx=6)
        router_select = tk.StringVar(value=nodes[0] if nodes else "")
        router_combo = ttk.Combobox(info_frame, values=nodes, textvariable=router_select, state="readonly")
        router_combo.pack(fill="x", padx=6)

        table = ttk.Treeview(info_frame, columns=("dest", "nexthop", "cost"), show="headings", height=8)
        table.heading("dest", text="Destination")
        table.heading("nexthop", text="Next hop")
        table.heading("cost", text="Cost")
        table.column("dest", width=100, anchor="w")
        table.column("nexthop", width=90, anchor="center")
        table.column("cost", width=50, anchor="center")
        table.pack(fill="both", expand=False, padx=6, pady=(6, 8))

        ttk.Label(info_frame, text="CLI / Configuration Log", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(6, 2), padx=6)
        cli_text = tk.Text(info_frame, height=12, wrap="word", bg="#f8fafc")
        cli_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        def append_cli(line: str) -> None:
            cli_text.insert("end", line + "\n")
            cli_text.see("end")

        def clear_cli() -> None:
            cli_text.delete("1.0", "end")

        def compute_routing_tables() -> dict[str, list[tuple[str, str, float]]]:
            if protocol_type != "ospf":
                tables: dict[str, list[tuple[str, str, float]]] = {}
                for r in nodes:
                    tables[r] = build_adaptive_routing_table(topology, r, active_edges=active_edges)
                return tables

            # Build adjacency with weights using active_edges
            adj: dict[str, list[tuple[str, float]]] = {n: [] for n in nodes}
            for e in topology.edges:
                key = tuple(sorted((e.source, e.target)))
                if key in active_edges:
                    adj[e.source].append((e.target, e.weight))
                    adj[e.target].append((e.source, e.weight))

            def dijkstra(src: str) -> dict[str, tuple[float, str]]:
                dist: dict[str, float] = {n: float("inf") for n in nodes}
                prev: dict[str, str | None] = {n: None for n in nodes}
                dist[src] = 0.0
                pq = [(0.0, src)]
                while pq:
                    d, u = heapq.heappop(pq)
                    if d > dist[u]:
                        continue
                    for v, w in adj.get(u, []):
                        nd = d + w
                        if nd < dist[v]:
                            dist[v] = nd
                            prev[v] = u
                            heapq.heappush(pq, (nd, v))
                # build next-hop mapping
                routing: dict[str, tuple[float, str]] = {}
                for dest in nodes:
                    if dest == src:
                        continue
                    if dist[dest] == float("inf"):
                        routing[dest] = (float("inf"), "-")
                        continue
                    # walk back to find next-hop
                    cur = dest
                    prev_hop = None
                    while prev[cur] is not None and prev[cur] != src:
                        cur = prev[cur]
                    next_hop = cur if prev[cur] is not None else dest if prev[dest] == src else cur
                    if prev[dest] is None and src != dest:
                        # direct neighbor
                        next_hop = dest if any(v == dest for v, _ in adj[src]) else "-"
                    routing[dest] = (dist[dest], next_hop)
                return routing

            tables: dict[str, list[tuple[str, str, float]]] = {}
            for r in nodes:
                rt = dijkstra(r)
                entries = []
                for dest, (cost, next_hop) in rt.items():
                    entries.append((dest, next_hop, cost if cost != float("inf") else float("inf")))
                tables[r] = entries
            return tables

        def update_table_view(router: str) -> None:
            table.delete(*table.get_children())
            tables = compute_routing_tables()
            for dest, nh, cost in tables.get(router, []):
                cost_str = "inf" if cost == float("inf") else f"{cost:.1f}"
                table.insert("", "end", values=(dest, nh, cost_str))

        router_combo.bind("<<ComboboxSelected>>", lambda e: update_table_view(router_select.get()))

        def draw_sim_topo(highlight_nodes: set[str] | None = None):
            canvas.delete("all")
            # draw edges
            for edge in topology.edges:
                key = tuple(sorted((edge.source, edge.target)))
                if key not in active_edges:
                    color = "#475569"
                    dash = (4, 4)
                else:
                    color = "#94a3b8"
                    dash = None
                x1, y1 = positions[edge.source]
                x2, y2 = positions[edge.target]
                canvas.create_line(x1, y1, x2, y2, fill=color, width=3, dash=dash)

            # draw nodes
            for node in nodes:
                x, y = positions[node]
                node_radius = 16
                fill = "#22c55e" if (not highlight_nodes or node not in highlight_nodes) else "#f97316"
                canvas.create_oval(x - node_radius, y - node_radius, x + node_radius, y + node_radius, fill=fill, outline="#bbf7d0", width=2, tags=(f"node_{node}"))
                canvas.create_text(x, y, text=node, fill="#07111f", font=("Segoe UI", 9, "bold"))

        def disconnect_selected():
            name = selected_edge.get()
            if not name:
                return
            a, b = name.split("-")
            key = tuple(sorted((a, b)))
            if key in active_edges:
                active_edges.remove(key)
            append_cli(f"Link {a}-{b} disconnected by operator.")
            update_table_view(router_select.get())
            draw_sim_topo()

        def restore_links():
            nonlocal active_edges
            active_edges = {tuple(sorted((e.source, e.target))) for e in topology.edges}
            append_cli("All links restored by operator.")
            update_table_view(router_select.get())
            draw_sim_topo()

        def compute_affected_nodes() -> list[str]:
            # find focus edge
            event = topology.event or {}
            if event.get("type") == "link_weight_change" and isinstance(event.get("edge"), (list, tuple)):
                seeds = {str(event["edge"][0]), str(event["edge"][1])}
            else:
                seeds = {topology.edges[0].source, topology.edges[0].target}

            # BFS up to depth 2
            graph = topology.adjacency()
            seen = set(seeds)
            frontier = deque((s, 0) for s in seeds)
            while frontier:
                node, depth = frontier.popleft()
                if depth >= 2:
                    continue
                for neighbor, _ in graph.get(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        frontier.append((neighbor, depth + 1))
            return list(seen)

        anim_jobs = []

        def reachable_nodes() -> set[str]:
            # Build adjacency only using active edges
            graph: dict[str, list[str]] = {n: [] for n in nodes}
            for e in topology.edges:
                key = tuple(sorted((e.source, e.target)))
                if key in active_edges:
                    graph.setdefault(e.source, []).append(e.target)
                    graph.setdefault(e.target, []).append(e.source)
            # BFS from first node to find reachable set
            start = None
            for n in nodes:
                if graph.get(n):
                    start = n
                    break
            if start is None:
                return set()
            seen = {start}
            q = deque([start])
            while q:
                cur = q.popleft()
                for nb in graph.get(cur, []):
                    if nb not in seen:
                        seen.add(nb)
                        q.append(nb)
            return seen

        def run_simulation():
            # cancel previous animations
            for job in anim_jobs:
                try:
                    canvas.after_cancel(job)
                except Exception:
                    pass
            anim_jobs.clear()
            reachable = reachable_nodes()

            # prepare edge delay map (ms)
            edge_delay_ms: dict[tuple[str, str], int] = {}
            for e in topology.edges:
                key = tuple(sorted((e.source, e.target)))
                edge_delay_ms[key] = max(50, int(e.delay * 150))

            # determine seeds
            event = topology.event or {}
            if event.get("type") == "link_weight_change" and isinstance(event.get("edge"), (list, tuple)):
                seeds = [str(event["edge"][0]), str(event["edge"][1])]
            else:
                seeds = [topology.edges[0].source, topology.edges[0].target]

            # BFS-like propagation scheduling
            start_time = 50
            detection_ms = 80
            recompute_offset = 60

            # previous routing tables to detect configuration changes
            prev_tables = compute_routing_tables()

            events: list[tuple[int, str, dict]] = []  # (time_ms, message, meta)

            # initial detection events
            for s in seeds:
                events.append((start_time, f"t={start_time:04d}ms: {s} detects link change", {"node": s}))

            # propagation queue: node, time_ms, depth, sender
            q = deque((s, start_time + detection_ms, 0, None) for s in seeds)
            seen: set[str] = set(seeds)
            while q:
                node, tnow, depth, sender = q.popleft()
                # send updates to neighbors
                for nb, _ in topology.adjacency().get(node, []):
                    key = tuple(sorted((node, nb)))
                    if key not in active_edges:
                        continue
                    if nb in seen:
                        continue
                    # respect AOSPF depth limit
                    if protocol_type == "aospf" and depth >= 2:
                        continue
                    d_ms = edge_delay_ms.get(key, 120)
                    send_time = tnow + 10
                    arrive_time = tnow + d_ms
                    events.append((send_time, f"t={send_time:04d}ms: {node} -> {nb} SEND LSUpdate (link {node}-{nb}, delay {d_ms}ms)", {"from": node, "to": nb, "link": key}))
                    events.append((arrive_time, f"t={arrive_time:04d}ms: {nb} RECEIVED LSUpdate from {node}", {"node": nb, "from": node}))
                    events.append((arrive_time + recompute_offset, f"t={arrive_time + recompute_offset:04d}ms: {nb} recomputes SPF", {"node": nb}))
                    seen.add(nb)
                    q.append((nb, arrive_time, depth + 1, node))

            # sort events by scheduled time
            events.sort(key=lambda x: x[0])

            clear_cli()
            append_cli(f"Starting {display_protocol} simulation...")
            update_table_view(router_select.get())
            draw_sim_topo()

            # schedule events and associated UI updates
            for time_ms, msg, meta in events:

                def make_handler(message: str, meta_info: dict, tms: int):
                    def handler():
                        append_cli(message)
                        # highlight receiver node if present
                        node = meta_info.get("node") or meta_info.get("to")
                        if node:
                            tag = f"node_{node}"
                            try:
                                canvas.itemconfigure(tag, fill="#f97316")
                            except Exception:
                                pass
                            # unhighlight shortly after
                            anim_jobs.append(canvas.after(180, lambda: canvas.itemconfigure(tag, fill="#22c55e")))
                        # on recompute, update routing table and emit configuration changes
                        if "recomputes" in message:
                            tables = compute_routing_tables()
                            # compare for the recomputing node
                            node_r = meta_info.get("node")
                            if node_r and node_r in tables:
                                prev = {d: (nh, c) for d, nh, c in prev_tables.get(node_r, [])}
                                for dest, nh, cost in tables[node_r]:
                                    prev_entry = prev.get(dest)
                                    cost_str = "inf" if cost == float("inf") else f"{cost:.1f}"
                                    if prev_entry is None or prev_entry[0] != nh or prev_entry[1] != cost:
                                        append_cli(f"t={tms:04d}ms: configure {node_r}: route {dest} -> {nh} cost {cost_str}")
                                prev_tables.update({node_r: tables[node_r]})

                    return handler

                anim_jobs.append(canvas.after(time_ms, make_handler(msg, meta, time_ms)))


        run_btn.config(command=run_simulation)
        disc_btn.config(command=disconnect_selected)
        restore_btn.config(command=restore_links)

        draw_sim_topo()

    def run_comparison(self) -> None:
        try:
            comparison = compare_topology_file(self.topology_path.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Comparison failed", str(exc))
            return

        self._comparison = comparison
        self._update_metrics()
        self._draw_bar_chart()
        self._draw_timeline()
        self._draw_topology()
        self._write_report()

    def _update_metrics(self) -> None:
        assert self._comparison is not None
        ospf = self._comparison["ospf"]
        fast = self._comparison["fast"]

        for item in self.metrics.get_children():
            self.metrics.delete(item)

        rows = [
            ("Total convergence", f"{ospf.total_time:.2f}", f"{fast.total_time:.2f}"),
            ("Messages", str(ospf.messages), str(fast.messages)),
            ("Affected nodes", str(ospf.affected_nodes), str(fast.affected_nodes)),
            ("Affected edges", str(ospf.affected_edges), str(fast.affected_edges)),
            ("Improvement (AOSPF)", "Baseline", f"{self._comparison['improvement_percent']:.1f}% faster"),
        ]
        for row in rows:
            self.metrics.insert("", "end", values=row)

    def _draw_bar_chart(self) -> None:
        assert self._comparison is not None
        canvas = self.bar_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 900)
        height = int(canvas["height"])
        margin = 60
        bar_width = 170
        spacing = 120
        baseline = height - 50

        canvas.create_text(margin, 25, anchor="w", fill="#e2e8f0", font=("Segoe UI", 13, "bold"), text="Total Convergence Time")
        canvas.create_line(margin, baseline, width - margin, baseline, fill="#334155", width=2)

        ospf = self._comparison["ospf"]
        fast = self._comparison["fast"]
        max_time = max(ospf.total_time, fast.total_time)
        scale = (height - 120) / max_time if max_time else 1.0

        bars = [
            (ospf.name, ospf.total_time, "#f97316"),
            (fast.name, fast.total_time, "#22c55e"),
        ]
        start_x = margin + 120
        for index, (label, value, color) in enumerate(bars):
            x0 = start_x + index * (bar_width + spacing)
            bar_height = value * scale
            y0 = baseline - bar_height
            canvas.create_rectangle(x0, y0, x0 + bar_width, baseline, fill=color, outline="")
            canvas.create_text(x0 + bar_width / 2, baseline + 18, text=label, fill="#e2e8f0", font=("Segoe UI", 9, "bold"), width=bar_width)
            canvas.create_text(x0 + bar_width / 2, y0 - 12, text=f"{value:.2f}", fill="#f8fafc", font=("Segoe UI", 11, "bold"))

        canvas.create_text(margin, height - 18, anchor="w", fill="#94a3b8", text="Lower is better")

    def _draw_timeline(self) -> None:
        assert self._comparison is not None
        canvas = self.timeline_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 900)
        height = int(canvas["height"])
        margin = 60
        baseline = height - 45

        canvas.create_text(margin, 25, anchor="w", fill="#e2e8f0", font=("Segoe UI", 13, "bold"), text="Cumulative Convergence Timeline")
        canvas.create_line(margin, baseline, width - margin, baseline, fill="#334155", width=2)
        canvas.create_line(margin, 50, margin, baseline, fill="#334155", width=2)

        timeline = self._comparison["timeline"]
        series = [
            (self._comparison["ospf"].name, timeline[self._comparison["ospf"].name], "#f97316"),
            (self._comparison["fast"].name, timeline[self._comparison["fast"].name], "#22c55e"),
        ]
        phases = ["Detect", "Flood", "Recompute", "Stabilize"]
        max_time = max(values[-1] for _, values, _ in series)
        scale_x = (width - 2 * margin) / 4
        scale_y = (baseline - 70) / max_time if max_time else 1.0

        for i, phase in enumerate(phases):
            x = margin + (i + 1) * scale_x
            canvas.create_line(x, baseline, x, baseline + 6, fill="#64748b")
            canvas.create_text(x, baseline + 20, text=phase, fill="#cbd5e1", font=("Segoe UI", 9))

        for name, values, color in series:
            points = []
            for i, value in enumerate(values):
                x = margin + (i + 1) * scale_x
                y = baseline - (value * scale_y)
                points.extend([x, y])
            canvas.create_line(points, fill=color, width=3, smooth=True)
            for i, value in enumerate(values):
                x = margin + (i + 1) * scale_x
                y = baseline - (value * scale_y)
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="")
            canvas.create_text(width - margin, 62 + (0 if color == "#f97316" else 18), anchor="e", fill=color, text=name, font=("Segoe UI", 9, "bold"))

    def _draw_topology(self) -> None:
        assert self._comparison is not None
        canvas = self.topology_canvas
        canvas.delete("all")

        topology = self._comparison["topology"]
        width = max(canvas.winfo_width(), 900)
        height = int(canvas["height"])
        center_x = width / 2
        center_y = height / 2 + 10
        radius = min(width, height) * 0.34

        canvas.create_text(24, 20, anchor="w", fill="#e2e8f0", font=("Segoe UI", 13, "bold"), text="Topology Layout")
        canvas.create_text(24, 44, anchor="w", fill="#94a3b8", font=("Segoe UI", 9), text="Nodes are arranged on a circle; the selected event edge is highlighted.")

        nodes = list(topology.nodes)
        positions: dict[str, tuple[float, float]] = {}
        for index, node in enumerate(nodes):
            angle = (2 * pi * index / max(1, len(nodes))) - pi / 2
            x = center_x + radius * cos(angle)
            y = center_y + radius * sin(angle)
            positions[node] = (x, y)

        event = topology.event or {}
        focus_edge = None
        if event.get("type") == "link_weight_change" and isinstance(event.get("edge"), (list, tuple)) and len(event["edge"]) >= 2:
            focus_edge = tuple(sorted((str(event["edge"][0]), str(event["edge"][1]))))

        for edge in topology.edges:
            x1, y1 = positions[edge.source]
            x2, y2 = positions[edge.target]
            edge_key = tuple(sorted((edge.source, edge.target)))
            color = "#f97316" if edge_key == focus_edge else "#475569"
            width_px = 4 if edge_key == focus_edge else 2
            canvas.create_line(x1, y1, x2, y2, fill=color, width=width_px)

        for node in nodes:
            x, y = positions[node]
            node_radius = 18
            canvas.create_oval(x - node_radius, y - node_radius, x + node_radius, y + node_radius, fill="#22c55e", outline="#bbf7d0", width=2)
            canvas.create_text(x, y, text=node, fill="#07111f", font=("Segoe UI", 9, "bold"))

        if event.get("type") == "link_weight_change" and focus_edge is not None:
            canvas.create_text(24, height - 24, anchor="w", fill="#fb7185", font=("Segoe UI", 9, "bold"), text=f"Event edge changed: {focus_edge[0]} - {focus_edge[1]}")
        else:
            canvas.create_text(24, height - 24, anchor="w", fill="#94a3b8", font=("Segoe UI", 9), text="No event edge specified in the topology file.")

    def _write_report(self) -> None:
        assert self._comparison is not None
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", format_report(self._comparison))
        self.report_text.see("1.0")


def run_app() -> None:
    app = ComparisonApp()
    app.mainloop()
