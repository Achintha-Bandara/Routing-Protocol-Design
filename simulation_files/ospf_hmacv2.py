import tkinter as tk
from tkinter import ttk
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import json
import os
import hmac
import hashlib
import secrets

# -------------------------------------------------------
# HMAC SECURITY LAYER
# -------------------------------------------------------
OSPF_HMAC_KEY = secrets.token_bytes(32)   # Shared secret — all legitimate routers know this
HMAC_ALGORITHM = "sha256"

def compute_lsa_hmac(lsa_payload: dict) -> str:
    canonical = (
        f"{lsa_payload['router_id']}|"
        f"{lsa_payload['sequence_num']}|"
        f"{lsa_payload['ttl']}|"
        f"{sorted(lsa_payload['neighbors'].items())}"
    ).encode()
    return hmac.new(OSPF_HMAC_KEY, canonical, HMAC_ALGORITHM).hexdigest()

def sign_lsa(lsa_payload: dict) -> dict:
    signed = dict(lsa_payload)
    signed["hmac"] = compute_lsa_hmac(lsa_payload)
    return signed

def verify_lsa(lsa_payload: dict) -> tuple:
    if "hmac" not in lsa_payload:
        return False, "REJECTED — No HMAC tag present (unsigned / forged packet)"
    expected = compute_lsa_hmac(lsa_payload)
    received = lsa_payload.get("hmac", "")
    if hmac.compare_digest(expected, received):
        return True, f"ACCEPTED — HMAC-SHA256 verified (tag ...{received[-8:]})"
    else:
        return False, (f"REJECTED — HMAC mismatch: got ...{received[-8:]}, "
                       f"expected ...{expected[-8:]} (packet forged or tampered)")

class OSPFAsynchronousWorkspaceDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("OSPF Unified Engine — HMAC-SHA256 Secured")
        self.root.geometry("1600x980")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.hello_interval = 3000
        self.dead_interval = 10000
        self.attack_injected = False
        self.attack_inject_time = None

        self.G = nx.Graph()
        self._load_topology()

    # ----------------------------------------------------------
    def _load_topology(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        topology_path = os.path.join(script_dir, 'topology.json')
        if not os.path.exists(topology_path):
            raise FileNotFoundError(f"topology.json not found at: {topology_path}")

        with open(topology_path, 'r') as f:
            data = json.load(f)

        self.node_positions = {}
        for node in data.get('nodes', []):
            self.node_positions[node['id']] = (node['x'], node['y'])

        self.edges_definition = []
        self.original_edges_data = {}
        self.G.clear()
        REFERENCE_BW_MBPS = 1000

        def parse_bw(bw_str):
            import re
            m = re.match(r'(\d+(?:\.\d+)?)(Gbps|Mbps|Kbps)', bw_str, re.IGNORECASE)
            if not m: return 100.0
            val, unit = float(m.group(1)), m.group(2).lower()
            return val * 1000 if unit == 'gbps' else (val if unit == 'mbps' else val / 1000)

        import math
        for edge in data.get('edges', []):
            u, v = edge['from'], edge['to']
            bw_str = edge.get('bandwidth', '100Mbps')
            delay = edge.get('delay', 10)
            bw_mbps = parse_bw(bw_str)
            cost = max(1, math.ceil(REFERENCE_BW_MBPS / bw_mbps))
            self.edges_definition.append((u, v, cost, delay))
            self.G.add_edge(u, v, cost=cost, bandwidth=bw_str, delay=delay)
            self.original_edges_data[tuple(sorted((u, v)))] = {
                'cost': cost, 'bandwidth': bw_str, 'bandwidth_mbps': bw_mbps, 'delay': delay
            }

        all_nodes = sorted(self.node_positions.keys())
        self.selected_node = all_nodes[0] if all_nodes else 'A'
        self.node_processing_delay = 3
        self.simulation_started = False
        self.current_time_ms = 0
        self.max_sim_time = 25000
        self.selected_edge = None
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []

        self.setup_ui()
        self.reset_simulation()

    def on_closing(self):
        plt.close('all')
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    # -------------------------------------------------------
    # SIMULATION LIFECYCLE
    # -------------------------------------------------------
    def start_simulation(self):
        self.hello_interval = int(self.hello_combo.get())
        self.dead_interval = self.hello_interval * 4
        self.current_time_ms = 0
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []
        self.selected_edge = None
        self.attack_injected = False
        self.attack_inject_time = None
        self.run_continuous_event_simulation()
        self.simulation_started = True
        self.hello_combo.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.attack_btn.config(state="normal")
        self.prev_btn.config(state="normal")
        self.next_btn.config(state="normal")
        self.sync_btn.config(state="normal")
        self.reset_btn.config(state="normal")
        self.render_all_views()

    def reset_simulation(self):
        self.simulation_started = False
        self.current_time_ms = 0
        self.selected_edge = None
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []
        self.attack_injected = False
        self.attack_inject_time = None
        self.hello_combo.config(state="readonly")
        self.start_btn.config(state="normal")
        self.attack_btn.config(state="disabled")
        self.prev_btn.config(state="disabled")
        self.next_btn.config(state="disabled")
        self.sync_btn.config(state="disabled")
        self.reset_btn.config(state="normal")
        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        self.flood_log.insert(tk.END, "SYSTEM IDLE — Click 'Start Simulation' to begin.")
        self.flood_log.config(state=tk.DISABLED)
        self.convergence_log_box.config(state=tk.NORMAL)
        self.convergence_log_box.delete('1.0', tk.END)
        self.convergence_log_box.insert(tk.END, "Awaiting simulation...")
        self.convergence_log_box.config(state=tk.DISABLED)
        self.flood_matrix_text.delete('1.0', tk.END)
        self.table_view_box.delete('1.0', tk.END)
        self.lsa_view_box.delete('1.0', tk.END)
        self.local_router_log_box.config(state=tk.NORMAL)
        self.local_router_log_box.delete('1.0', tk.END)
        self.local_router_log_box.insert(tk.END, "Adjacency offline.")
        self.local_router_log_box.config(state=tk.DISABLED)
        self.convergence_indicator_lbl.config(text="Simulation Not Started", bg="#dcdde1", fg="#2c3e50")
        self.hmac_banner.config(text="HMAC-SHA256 security layer active — all LSAs signed on transmit", bg="#2c3e50", fg="#dfe6e9")
        self.render_base_configuration_graph()

    def inject_fake_lsa(self):
        if not self.simulation_started:
            return
        self.attack_injected = True
        self.attack_inject_time = self.current_time_ms
        self.run_continuous_event_simulation()
        self.render_all_views()
        self.hmac_banner.config(
            text=f"ATTACK LSA injected at t={self.attack_inject_time}ms — HMAC verification BLOCKED it (see Global Log)",
            bg="#c0392b", fg="white"
        )

    def toggle_selected_link(self):
        if self.selected_edge and self.simulation_started:
            self.link_toggles.append((self.selected_edge, self.current_time_ms))
            self.run_continuous_event_simulation()
            self.render_all_views()

    def apply_runtime_delay_change(self, event=None):
        if self.selected_edge and self.simulation_started:
            new_delay = int(self.delay_change_combo.get())
            self.delay_changes.append((self.selected_edge, new_delay, self.current_time_ms))
            u, v = self.selected_edge
            self.logs_database.append({
                "time": self.current_time_ms,
                "text": f"PROPAGATION MOD: delay on {u}-{v} changed to {new_delay}ms.",
                "routers": [u, v], "type": "process"
            })
            self.run_continuous_event_simulation()
            self.render_all_views()

    def apply_runtime_cost_change(self, event=None):
        if self.selected_edge and self.simulation_started:
            new_cost = int(self.cost_change_combo.get())
            self.cost_changes.append((self.selected_edge, new_cost, self.current_time_ms))
            u, v = self.selected_edge
            self.logs_database.append({
                "time": self.current_time_ms,
                "text": f"COST MOD: OSPF cost on {u}-{v} changed to {new_cost}. Re-flooding triggered.",
                "routers": [u, v], "type": "process"
            })
            self.run_continuous_event_simulation()
            self.render_all_views()

    def skip_to_synchronize(self):
        if self.simulation_started:
            t = self.current_time_ms
            if self.timeline_states[t]["is_true_converged"]:
                while t <= self.max_sim_time and self.timeline_states[t]["is_true_converged"]:
                    t += 1
            while t <= self.max_sim_time:
                if self.timeline_states[t]["is_true_converged"]:
                    self.current_time_ms = t
                    break
                t += 1
            self.render_all_views()

    # -------------------------------------------------------
    # DISCRETE EVENT SIMULATION ENGINE
    # -------------------------------------------------------
    def run_continuous_event_simulation(self):
        nodes = sorted(list(self.G.nodes()))

        current_lsdb = {n: {} for n in nodes}
        adj_states = {n: {nbr: "DOWN" for nbr in self.G.neighbors(n)} for n in nodes}
        last_hello_time = {n: {nbr: 0 for nbr in self.G.neighbors(n)} for n in nodes}
        lsa_seq = {n: 1 for n in nodes}
        lsa_triggered = {n: False for n in nodes}
        broken_links = set()
        event_queue = []
        self.logs_database = []
        self.router_events = {n: [] for n in nodes}
        self.convergence_metrics_database = []
        pending_failure_tracks = []

        def get_current_delay(u_node, v_node, eval_time):
            e = tuple(sorted((u_node, v_node)))
            base = self.original_edges_data[e]['delay']
            for me, md, mt in self.delay_changes:
                if me == e and mt <= eval_time: base = md
            return base

        def get_current_cost(u_node, v_node, eval_time):
            e = tuple(sorted((u_node, v_node)))
            base = self.original_edges_data[e]['cost']
            for me, mc, mt in self.cost_changes:
                if me == e and mt <= eval_time: base = mc
            return base

        self.logs_database.append({
            "time": 0,
            "text": (f"[BOOT] All routers initialised. HELLO interval={self.hello_interval}ms. "
                     f"HMAC-SHA256 signing enabled (shared key ...{OSPF_HMAC_KEY.hex()[-8:]})."),
            "routers": list(nodes), "type": "init"
        })
        for n in nodes:
            event_queue.append((0, "HELLO_SEND", (n,)))

        # Seed attack event if requested
        if self.attack_injected and self.attack_inject_time is not None:
            event_queue.append((self.attack_inject_time, "FAKE_LSA_INJECT", ()))

        self.timeline_states = {}
        last_logged_state = "RED"
        initial_sync_logged = False
        last_protocol_instability = 0
        last_true_instability = 0
        current_time = 0

        while current_time <= self.max_sim_time:
            active_protocol_disruption = False

            # Runtime link toggles
            for edge, toggle_time in self.link_toggles:
                if toggle_time == current_time:
                    u, v = edge
                    if edge in broken_links:
                        broken_links.remove(edge)
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"LINK RESTORED: {u}↔{v} is UP. Awaiting periodic HELLO rediscovery.",
                            "routers": [u, v], "type": "process"
                        })
                        self.router_events[u].append((current_time, f"Link to {v} restored. Waiting for HELLO.", "init"))
                        self.router_events[v].append((current_time, f"Link to {u} restored. Waiting for HELLO.", "init"))
                    else:
                        broken_links.add(edge)
                        pending_failure_tracks.append({"edge": edge, "t_fail": current_time, "t_timeout": None})
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"LINK SEVERED: {u}↔{v} is DOWN. Dropping packets, waiting for dead timer.",
                            "routers": [u, v], "type": "dropped"
                        })
                        self.router_events[u].append((current_time, f"Link to {v} broken. Dead timer running.", "dropped"))
                        self.router_events[v].append((current_time, f"Link to {u} broken. Dead timer running.", "dropped"))

            # Runtime cost changes
            for edge, new_c, c_time in self.cost_changes:
                if c_time == current_time:
                    u, v = edge
                    active_protocol_disruption = True
                    for r in [u, v]:
                        lsa_seq[r] += 1
                        active_nbrs = {k: get_current_cost(r, k, current_time)
                                       for k in self.G.neighbors(r) if adj_states[r][k] == "2WAY"}
                        lsa_payload = sign_lsa({"router_id": r, "sequence_num": lsa_seq[r], "ttl": 64, "neighbors": active_nbrs})
                        current_lsdb[r][r] = lsa_payload
                        self.router_events[r].append((current_time, f"Cost change triggered new LSA (Seq:{lsa_seq[r]}, HMAC signed).", "db_update"))
                        for fn in self.G.neighbors(r):
                            if adj_states[r][fn] == "2WAY":
                                d = get_current_delay(r, fn, current_time)
                                event_queue.append((current_time + d, "LSA_ARRIVE", (r, fn, lsa_payload, d)))

            # Dead timer checks
            for u in nodes:
                for nbr in self.G.neighbors(u):
                    if adj_states[u][nbr] in ["INIT", "2WAY"]:
                        if current_time - last_hello_time[u][nbr] >= self.dead_interval:
                            adj_states[u][nbr] = "DOWN"
                            active_protocol_disruption = True
                            te = tuple(sorted((u, nbr)))
                            for item in pending_failure_tracks:
                                if item["edge"] == te and item["t_timeout"] is None:
                                    item["t_timeout"] = current_time
                            self.logs_database.append({
                                "time": current_time,
                                "text": f"DEAD TIMER EXPIRED: Router {u} lost adjacency to Router {nbr} ({self.dead_interval}ms without HELLO). Adjacency torn down.",
                                "routers": [u, nbr], "type": "dropped"
                            })
                            self.router_events[u].append((current_time, f"Dead timer expired for {nbr}. Adjacency DOWN.", "dropped"))
                            lsa_seq[u] += 1
                            active_nbrs = {k: get_current_cost(u, k, current_time)
                                           for k in self.G.neighbors(u) if adj_states[u][k] == "2WAY"}
                            lsa_payload = sign_lsa({"router_id": u, "sequence_num": lsa_seq[u], "ttl": 64, "neighbors": active_nbrs})
                            current_lsdb[u][u] = lsa_payload
                            self.router_events[u].append((current_time, f"Issued corrective LSA (Seq:{lsa_seq[u]}, HMAC signed) removing {nbr}.", "db_update"))
                            for fn in self.G.neighbors(u):
                                if adj_states[u][fn] == "2WAY":
                                    d = get_current_delay(u, fn, current_time)
                                    event_queue.append((current_time + d, "LSA_ARRIVE", (u, fn, lsa_payload, d)))
                                    self.router_events[u].append((current_time, f"Flooded corrective LSA to {fn}.", "sent"))

            event_queue.sort(key=lambda x: x[0])

            while event_queue and event_queue[0][0] == current_time:
                t_curr, ev_type, data = event_queue.pop(0)

                # ── HELLO_SEND ──
                if ev_type == "HELLO_SEND":
                    router = data[0]
                    active_neighbors = [k for k, v in adj_states[router].items() if v in ["INIT", "2WAY"]]
                    if current_time > 0:
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"HELLO sent from Router {router} (active neighbors: {active_neighbors}).",
                            "routers": [router], "type": "hello_tx"
                        })
                        self.router_events[router].append((current_time, "Sent periodic HELLO broadcast.", "hello_tx"))
                    for nbr in self.G.neighbors(router):
                        d = get_current_delay(router, nbr, current_time)
                        event_queue.append((current_time + d, "HELLO_ARRIVE", (router, nbr, list(active_neighbors), d)))
                    event_queue.append((current_time + self.hello_interval, "HELLO_SEND", (router,)))

                # ── HELLO_ARRIVE ──
                elif ev_type == "HELLO_ARRIVE":
                    sender, receiver, sender_nbr_list, link_delay = data
                    if tuple(sorted((sender, receiver))) in broken_links:
                        continue
                    last_hello_time[receiver][sender] = current_time
                    if receiver in sender_nbr_list:
                        if adj_states[receiver][sender] != "2WAY":
                            adj_states[receiver][sender] = "2WAY"
                            active_protocol_disruption = True
                            self.router_events[receiver].append((current_time, f"2-WAY adjacency formed with Router {sender}.", "hello_rx"))
                            lsa_triggered[receiver] = True
                            lsa_seq[receiver] += 1
                            active_nbrs = {k: get_current_cost(receiver, k, current_time)
                                           for k in self.G.neighbors(receiver) if adj_states[receiver][k] == "2WAY"}
                            lsa_payload = sign_lsa({"router_id": receiver, "sequence_num": lsa_seq[receiver], "ttl": 64, "neighbors": active_nbrs})
                            current_lsdb[receiver][receiver] = lsa_payload
                            tag_short = lsa_payload['hmac'][-8:]
                            self.logs_database.append({
                                "time": current_time,
                                "text": (f"[HMAC SIGN] Router {receiver} signed its Router-LSA "
                                         f"(Seq:{lsa_seq[receiver]}, neighbors:{list(active_nbrs.keys())}) "
                                         f"→ tag ...{tag_short}"),
                                "routers": [receiver], "type": "hmac_ok"
                            })
                            self.router_events[receiver].append((current_time, f"Signed and stored own LSA (Seq:{lsa_seq[receiver]}, HMAC tag ...{tag_short}).", "db_update"))
                            for nbr in self.G.neighbors(receiver):
                                if adj_states[receiver][nbr] == "2WAY":
                                    d = get_current_delay(receiver, nbr, current_time)
                                    event_queue.append((current_time + d, "LSA_ARRIVE", (receiver, nbr, lsa_payload, d)))
                                    self.router_events[receiver].append((current_time, f"Flooded LSA to Router {nbr}.", "sent"))
                        else:
                            self.logs_database.append({
                                "time": current_time,
                                "text": f"HELLO received at Router {receiver} from Router {sender}. Dead timer refreshed.",
                                "routers": [sender, receiver], "type": "hello_rx"
                            })
                            self.router_events[receiver].append((current_time, f"HELLO from {sender} — dead timer reset to {self.dead_interval}ms.", "hello_rx"))
                    else:
                        if adj_states[receiver][sender] == "DOWN":
                            adj_states[receiver][sender] = "INIT"
                            active_protocol_disruption = True
                            self.router_events[receiver].append((current_time, f"Router {sender} → INIT. Sending reactive HELLO.", "process"))
                            t_resp = current_time + self.node_processing_delay + link_delay
                            reactive_nbrs = [k for k, v in adj_states[receiver].items() if v in ["INIT", "2WAY"]]
                            event_queue.append((t_resp, "HELLO_ARRIVE", (receiver, sender, list(reactive_nbrs), link_delay)))

                # ── LSA_ARRIVE ──
                elif ev_type == "LSA_ARRIVE":
                    sender, receiver, incoming_payload, link_delay = data
                    if tuple(sorted((sender, receiver))) in broken_links:
                        # Only skip broken-link check for ATTACK (not in graph)
                        if sender != "ATTACK":
                            continue

                    active_protocol_disruption = True
                    owner = incoming_payload["router_id"]

                    # HMAC verification — the key gate
                    hmac_ok, hmac_reason = verify_lsa(incoming_payload)

                    self.logs_database.append({
                        "time": current_time,
                        "text": (f"[LSA ARRIVAL] Router {receiver} received LSA from {sender} "
                                 f"(Origin: Router_{owner}, Seq:{incoming_payload['sequence_num']})  →  "
                                 f"HMAC: {hmac_reason}"),
                        "routers": [sender, receiver],
                        "type": "hmac_ok" if hmac_ok else "hmac_fail"
                    })
                    self.router_events[receiver].append((
                        current_time,
                        f"LSA from {sender} (Origin:{owner}, Seq:{incoming_payload['sequence_num']}). HMAC: {hmac_reason}",
                        "received" if hmac_ok else "dropped"
                    ))

                    if not hmac_ok:
                        self.logs_database.append({
                            "time": current_time,
                            "text": (f"[SECURITY DROP] Router {receiver} DISCARDED LSA from Router_{owner} — "
                                     f"{hmac_reason}. LSDB is unchanged. Attack neutralised."),
                            "routers": [receiver], "type": "hmac_fail"
                        })
                        continue   # Do NOT install or re-flood

                    # HMAC OK — check sequence number
                    cached_seq = current_lsdb[receiver].get(owner, {}).get("sequence_num", 0)
                    if incoming_payload["sequence_num"] > cached_seq:
                        t_proc = current_time + self.node_processing_delay
                        event_queue.append((t_proc, "LSA_PROCESS", (receiver, incoming_payload, sender)))
                        self.logs_database.append({
                            "time": current_time,
                            "text": (f"[ACCEPTED] Router {receiver}: LSA for Router_{owner} "
                                     f"Seq {incoming_payload['sequence_num']} > cached {cached_seq}. "
                                     f"Scheduled LSDB install in +{self.node_processing_delay}ms."),
                            "routers": [receiver], "type": "received"
                        })
                        self.router_events[receiver].append((current_time, f"LSA accepted (Seq {incoming_payload['sequence_num']} > cached {cached_seq}). Processing in +{self.node_processing_delay}ms.", "process"))
                    else:
                        self.logs_database.append({
                            "time": current_time,
                            "text": (f"[DUPLICATE SUPPRESSED] Router {receiver}: LSA for Router_{owner} "
                                     f"Seq {incoming_payload['sequence_num']} already cached "
                                     f"(cached seq={cached_seq}). No action needed."),
                            "routers": [receiver], "type": "process"
                        })
                        self.router_events[receiver].append((current_time, f"Duplicate LSA for {owner} (Seq {incoming_payload['sequence_num']} ≤ {cached_seq}). Suppressed.", "dropped"))

                # ── LSA_PROCESS ──
                elif ev_type == "LSA_PROCESS":
                    router, incoming_payload, arrival_port = data
                    active_protocol_disruption = True
                    owner = incoming_payload["router_id"]
                    cached_seq = current_lsdb[router].get(owner, {}).get("sequence_num", 0)
                    if incoming_payload["sequence_num"] > cached_seq:
                        current_lsdb[router][owner] = incoming_payload
                        self.logs_database.append({
                            "time": current_time,
                            "text": (f"[LSDB UPDATED] Router {router} installed Router_{owner} LSA "
                                     f"(Seq:{incoming_payload['sequence_num']}, "
                                     f"neighbors:{list(incoming_payload['neighbors'].keys())})."),
                            "routers": [router], "type": "db_update"
                        })
                        self.router_events[router].append((current_time, f"Installed Router_{owner} LSA in LSDB (Seq:{incoming_payload['sequence_num']}).", "db_update"))
                        for nbr in self.G.neighbors(router):
                            if nbr != arrival_port and adj_states[router][nbr] == "2WAY":
                                d = get_current_delay(router, nbr, current_time)
                                event_queue.append((current_time + d, "LSA_ARRIVE", (router, nbr, incoming_payload, d)))
                                self.router_events[router].append((current_time, f"Re-flooded Router_{owner} LSA to Router {nbr}.", "sent"))

                # ── FAKE_LSA_INJECT ──
                elif ev_type == "FAKE_LSA_INJECT":
                    all_nodes_sorted = sorted(list(self.G.nodes()))
                    atk_nbrs = {}
                    if len(all_nodes_sorted) >= 1: atk_nbrs[all_nodes_sorted[0]] = 1
                    if len(all_nodes_sorted) >= 2: atk_nbrs[all_nodes_sorted[1]] = 1

                    fake_lsa = {
                        "router_id": "ATTACK",
                        "sequence_num": 9999,
                        "ttl": 64,
                        "neighbors": atk_nbrs
                        # Deliberately NO "hmac" field
                    }

                    self.logs_database.append({
                        "time": current_time,
                        "text": (f"[ATTACK EVENT] Adversary router 'ATTACK' injects forged LSA "
                                 f"(Seq:9999, claiming neighbors {list(atk_nbrs.keys())}). "
                                 f"Packet has NO HMAC signature."),
                        "routers": list(nodes), "type": "hmac_fail"
                    })

                    # Try to deliver to every node that has at least one 2-WAY neighbor
                    delivered = 0
                    for n in nodes:
                        for nbr in self.G.neighbors(n):
                            if adj_states[n][nbr] == "2WAY":
                                d = get_current_delay(n, nbr, current_time)
                                event_queue.append((current_time + d, "LSA_ARRIVE", ("ATTACK", n, dict(fake_lsa), d)))
                                delivered += 1
                                break

                    if delivered == 0:
                        self.logs_database.append({
                            "time": current_time,
                            "text": "[ATTACK EVENT] No 2-WAY adjacencies found yet. Fake LSA could not be delivered. Try after convergence.",
                            "routers": [], "type": "hmac_fail"
                        })

            # ── CONVERGENCE CHECKS ──
            operational_nodes = [n for n in nodes if any(s == "2WAY" for s in adj_states[n].values())]
            is_synchronized = False
            if operational_nodes:
                ref_db = current_lsdb[operational_nodes[0]]
                is_synchronized = True
                for n in operational_nodes:
                    if current_lsdb[n].keys() != ref_db.keys():
                        is_synchronized = False; break
                    for k in ref_db:
                        if current_lsdb[n][k]["sequence_num"] != ref_db[k]["sequence_num"]:
                            is_synchronized = False; break

            is_physically_accurate = True
            for u, v in self.G.edges():
                et = tuple(sorted((u, v)))
                is_broken = et in broken_links
                for n in nodes:
                    u_has_v = v in current_lsdb[n].get(u, {}).get("neighbors", {})
                    v_has_u = u in current_lsdb[n].get(v, {}).get("neighbors", {})
                    if is_broken:
                        if u_has_v or v_has_u: is_physically_accurate = False; break
                    else:
                        if not (u_has_v and v_has_u): is_physically_accurate = False; break
                if not is_physically_accurate: break

            has_pending = any(ev[1] in ["LSA_ARRIVE", "LSA_PROCESS"] for ev in event_queue)
            if active_protocol_disruption or has_pending or not is_synchronized:
                last_protocol_instability = current_time
            is_protocol_converged = (current_time > last_protocol_instability) and len(operational_nodes) > 0

            if active_protocol_disruption or has_pending or not is_synchronized or not is_physically_accurate:
                last_true_instability = current_time
            is_true_converged = (current_time > last_true_instability) and len(operational_nodes) > 0

            current_state_str = "GREEN" if is_true_converged else ("YELLOW" if is_protocol_converged else "RED")

            if current_state_str != last_logged_state:
                if current_state_str == "GREEN":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "OSPF CONVERGED: All LSDBs synchronised and accurate to physical topology.",
                        "routers": list(nodes), "type": "converged"
                    })
                    if not initial_sync_logged:
                        initial_sync_logged = True
                        self.convergence_metrics_database.append({
                            "time": current_time, "type": "INITIAL",
                            "text": f"Initial convergence at t={current_time}ms from boot.\n"
                        })
                    for item in list(pending_failure_tracks):
                        if item["t_timeout"] is not None:
                            u, v = item["edge"]
                            self.convergence_metrics_database.append({
                                "time": current_time, "type": "DISRUPTION",
                                "text": (f"Link {u}-{v} failure recovery:\n"
                                         f"  Total time after failure: {current_time - item['t_fail']}ms\n"
                                         f"  Time after dead-timer: {current_time - item['t_timeout']}ms\n")
                            })
                            pending_failure_tracks.remove(item)
                elif current_state_str == "YELLOW":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "OSPF LSDBs synchronised but inaccurate to physical topology (discrepancy window).",
                        "routers": list(nodes), "type": "process"
                    })
                last_logged_state = current_state_str

            active_tx = []
            for t_f, type_f, data_f in event_queue:
                if type_f in ["LSA_ARRIVE", "HELLO_ARRIVE"]:
                    s_f, r_f, *extra = data_f
                    d_f = extra[-1]
                    t_start = t_f - d_f
                    if t_start <= current_time < t_f and tuple(sorted((s_f, r_f))) not in broken_links:
                        active_tx.append((s_f, r_f, t_start, t_f, type_f))

            self.timeline_states[current_time] = {
                "lsdb": {n: {k: dict(v) for k, v in current_lsdb[n].items()} for n in nodes},
                "active_links": list(active_tx),
                "broken_links": set(broken_links),
                "adj_states": {n: dict(adj_states[n]) for n in nodes},
                "is_protocol_converged": is_protocol_converged,
                "is_true_converged": is_true_converged,
                "true_convergence_time": last_true_instability if is_true_converged else -1,
                "get_delay_func": get_current_delay,
                "get_cost_func": get_current_cost
            }
            current_time += 1

    # -------------------------------------------------------
    # UI LAYOUT (SCROLLABLE LEFT PANEL)
    # -------------------------------------------------------
    def setup_ui(self):
        # Right column (graph)
        self.right_column = tk.Frame(self.root, padx=10, pady=10)
        self.right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Left scrollable container
        left_container = tk.Frame(self.root, width=630)   # 610 + padding
        left_container.pack(side=tk.LEFT, fill=tk.Y)
        left_container.pack_propagate(False)

        # Canvas and scrollbar
        self.left_canvas = tk.Canvas(left_container, highlightthickness=0)
        scrollbar = tk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame that will hold all left-side widgets
        self.left_column = tk.Frame(self.left_canvas, padx=10, pady=10)
        self.left_canvas.create_window((0, 0), window=self.left_column, anchor="nw", width=self.left_canvas.winfo_reqwidth())

        # Update scroll region when inner frame changes
        self.left_column.bind("<Configure>", self._on_left_column_configure)
        self.left_canvas.bind("<Configure>", self._on_left_canvas_configure)

        # Now build the actual panels inside self.left_column
        self.build_top_flooding_panel()
        self.build_bottom_inspector_panel()
        self.build_graph_canvas()

    def _on_left_column_configure(self, event=None):
        # Update scroll region to encompass inner frame
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def _on_left_canvas_configure(self, event):
        # Resize inner frame to fit canvas width
        self.left_canvas.itemconfig(1, width=event.width)

    def build_top_flooding_panel(self):
        flood_frame = tk.LabelFrame(self.left_column, text=" 1. LSA Flooding & Security Panel ", font=("Helvetica", 11, "bold"), fg="#2c3e50", padx=8, pady=8)
        flood_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Row 1: Hello interval + Start
        row1 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1, text="OSPF Hello Interval (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.hello_combo = ttk.Combobox(row1, values=["1000", "2000", "3000", "5000"], state="readonly", width=8)
        self.hello_combo.pack(side=tk.LEFT, padx=4)
        self.hello_combo.set("3000")
        self.start_btn = tk.Button(row1, text="Start Simulation", font=("Helvetica", 9, "bold"),
                                   command=self.start_simulation, bg="#27ae60", fg="white")
        self.start_btn.pack(side=tk.RIGHT, padx=4)

        # HMAC status banner
        self.hmac_banner = tk.Label(flood_frame,
                                    text="HMAC-SHA256 security layer active — all LSAs signed on transmit",
                                    font=("Helvetica", 9, "bold"), bg="#2c3e50", fg="#dfe6e9",
                                    bd=1, relief=tk.SOLID, pady=3)
        self.hmac_banner.pack(fill=tk.X, pady=(0, 4))

        # Row 2: Attack injection
        row2 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row2.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row2, text="Security Attack:", font=("Helvetica", 9, "bold"), fg="#c0392b").pack(side=tk.LEFT, padx=2)
        self.attack_btn = tk.Button(row2,
                                    text="Inject Fake LSA from ATTACK router (neighbors A, B)",
                                    font=("Helvetica", 9, "bold"),
                                    command=self.inject_fake_lsa,
                                    state="disabled",
                                    bg="#c0392b", fg="white", activebackground="#a93226")
        self.attack_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=4)

        # Row 3: Link disruption
        row3 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row3.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row3, text="Link Disruption:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.link_toggle_btn = tk.Button(row3, text="Select a Link on Map",
                                         font=("Helvetica", 9, "bold"), state="disabled",
                                         command=self.toggle_selected_link)
        self.link_toggle_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=4)

        # Row 4: Delay
        row4 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row4.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row4, text="Runtime Delay (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.delay_change_combo = ttk.Combobox(row4, values=["2","5","8","12","15","20","25","30","40","50"],
                                               state="disabled", width=8)
        self.delay_change_combo.pack(side=tk.RIGHT, padx=4)
        self.delay_change_combo.bind("<<ComboboxSelected>>", self.apply_runtime_delay_change)

        # Row 5: Cost
        row5 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row5.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row5, text="OSPF Cost Override:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.cost_change_combo = ttk.Combobox(row5, values=["1","2","3","4","5","10","15","20","50","100"],
                                              state="disabled", width=8)
        self.cost_change_combo.pack(side=tk.RIGHT, padx=4)
        self.cost_change_combo.bind("<<ComboboxSelected>>", self.apply_runtime_cost_change)

        # Step / navigation
        step_row = tk.Frame(flood_frame)
        step_row.pack(fill=tk.X, pady=2)
        tk.Label(step_row, text="Step Size (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.step_combo = ttk.Combobox(step_row, values=["5","10","50","100","1000"], state="readonly", width=8)
        self.step_combo.pack(side=tk.LEFT, padx=4)
        self.step_combo.set("100")

        nav_row = tk.Frame(flood_frame)
        nav_row.pack(fill=tk.X, pady=4)
        self.prev_btn = tk.Button(nav_row, text="◀ Prev", font=("Helvetica", 10, "bold"),
                                  command=self.prev_timeline_step, bg="#222f3e", fg="white")
        self.prev_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.next_btn = tk.Button(nav_row, text="Next ▶", font=("Helvetica", 10, "bold"),
                                  command=self.next_timeline_step, bg="#1e3799", fg="white")
        self.next_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=3)

        sc_row = tk.Frame(flood_frame)
        sc_row.pack(fill=tk.X, pady=2)
        self.sync_btn = tk.Button(sc_row, text="Skip to Convergence ⚡", font=("Helvetica", 9, "bold"),
                                  command=self.skip_to_synchronize, bg="#f39c12", fg="white")
        self.sync_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.reset_btn = tk.Button(sc_row, text="Reset Engine", font=("Helvetica", 9, "bold"),
                                   command=self.reset_simulation, bg="#7f8c8d", fg="white")
        self.reset_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        self.convergence_indicator_lbl = tk.Label(flood_frame, text="Simulation Not Started",
                                                  font=("Helvetica", 10, "bold"), bg="#dcdde1", fg="#2c3e50",
                                                  bd=1, relief=tk.SOLID, pady=3)
        self.convergence_indicator_lbl.pack(fill=tk.X, pady=4)

        tk.Label(flood_frame, text="LSDB Sync Matrix:", font=("Helvetica", 9, "bold"), fg="#34495e").pack(anchor=tk.W)
        self.flood_matrix_text = tk.Text(flood_frame, height=5, font=("Courier New", 9), bg="#f8f9fa", bd=1, relief=tk.SOLID)
        self.flood_matrix_text.pack(fill=tk.X)

        # Notebook: Global Commentary | Convergence
        nb = ttk.Notebook(flood_frame)
        nb.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tab_global = tk.Frame(nb)
        tab_conv = tk.Frame(nb)
        nb.add(tab_global, text=" Global Commentary Log ")
        nb.add(tab_conv, text=" Convergence Log ")

        sb1 = tk.Scrollbar(tab_global)
        sb1.pack(side=tk.RIGHT, fill=tk.Y)
        self.flood_log = tk.Text(tab_global, wrap=tk.WORD, font=("Helvetica", 9), bg="#efeef3",
                                 bd=0, padx=4, pady=4, yscrollcommand=sb1.set)
        self.flood_log.pack(fill=tk.BOTH, expand=True)
        sb1.config(command=self.flood_log.yview)

        sb2 = tk.Scrollbar(tab_conv)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.convergence_log_box = tk.Text(tab_conv, wrap=tk.WORD, font=("Courier New", 9),
                                           bg="#1e272e", fg="white", bd=0, padx=4, pady=4,
                                           yscrollcommand=sb2.set)
        self.convergence_log_box.pack(fill=tk.BOTH, expand=True)
        sb2.config(command=self.convergence_log_box.yview)

        # Tag styles
        self.flood_log.tag_config("init",      foreground="#7f8c8d")
        self.flood_log.tag_config("hello_tx",  foreground="#0984e3", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hello_rx",  foreground="#00b894", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("sent",      foreground="#1e3799", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("received",  foreground="#218c74", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("process",   foreground="#d35400")
        self.flood_log.tag_config("dropped",   foreground="#c0392b", font=("Helvetica", 9, "italic"))
        self.flood_log.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("converged", foreground="#1b1464", background="#fff200", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hmac_ok",   foreground="#155724", background="#d4edda", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hmac_fail", foreground="white",   background="#c0392b", font=("Helvetica", 9, "bold"))

        self.convergence_log_box.tag_config("INITIAL",    foreground="#2ecc71", font=("Courier New", 9, "bold"))
        self.convergence_log_box.tag_config("DISRUPTION", foreground="#f1c40f")

    def build_bottom_inspector_panel(self):
        inspect_frame = tk.LabelFrame(self.left_column, text=" 2. Local Router Inspector Panel ",
                                      font=("Helvetica", 11, "bold"), fg="#c0392b", padx=8, pady=8)
        inspect_frame.pack(fill=tk.BOTH, expand=True)

        self.packet_header_lbl = tk.Label(inspect_frame, text="LSA Packet Data: Router A",
                                          font=("Helvetica", 10, "bold"), fg="#c0392b")
        self.packet_header_lbl.pack(anchor=tk.W)
        self.lsa_view_box = tk.Text(inspect_frame, height=5, font=("Courier New", 9), bg="#fdf2f2",
                                    bd=1, relief=tk.SOLID, padx=4, pady=4)
        self.lsa_view_box.pack(fill=tk.X, pady=(0, 4))

        self.local_log_header_lbl = tk.Label(inspect_frame, text="Local Port Log for Router A:",
                                             font=("Helvetica", 10, "bold"), fg="#78281f")
        self.local_log_header_lbl.pack(anchor=tk.W)
        llc = tk.Frame(inspect_frame, bd=1, relief=tk.SOLID, height=100)
        llc.pack(fill=tk.X, pady=(0, 4))
        llc.pack_propagate(False)
        sb3 = tk.Scrollbar(llc)
        sb3.pack(side=tk.RIGHT, fill=tk.Y)
        self.local_router_log_box = tk.Text(llc, wrap=tk.WORD, font=("Helvetica", 9), bg="white",
                                            bd=0, padx=4, pady=4, yscrollcommand=sb3.set)
        self.local_router_log_box.pack(fill=tk.BOTH, expand=True)
        sb3.config(command=self.local_router_log_box.yview)

        for box in [self.local_router_log_box]:
            box.tag_config("init",      foreground="#7f8c8d")
            box.tag_config("hello_tx",  foreground="#0984e3", font=("Helvetica", 9, "bold"))
            box.tag_config("hello_rx",  foreground="#00b894", font=("Helvetica", 9, "bold"))
            box.tag_config("sent",      foreground="#1e3799", font=("Helvetica", 9, "bold"))
            box.tag_config("received",  foreground="#218c74", font=("Helvetica", 9, "bold"))
            box.tag_config("process",   foreground="#d35400")
            box.tag_config("dropped",   foreground="#c0392b", font=("Helvetica", 9, "italic"))
            box.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))

        # Routing table (with its own internal scrollbar)
        self.table_header_lbl = tk.Label(inspect_frame, text="Routing Table: Router A",
                                         font=("Helvetica", 10, "bold"), fg="#1b5c8f")
        self.table_header_lbl.pack(anchor=tk.W)
        tc = tk.Frame(inspect_frame, bd=1, relief=tk.SOLID)
        tc.pack(fill=tk.BOTH, expand=True)
        sb4 = tk.Scrollbar(tc)
        sb4.pack(side=tk.RIGHT, fill=tk.Y)
        self.table_view_box = tk.Text(tc, font=("Courier New", 9), bg="#f8f9fa", bd=0, padx=4, pady=4,
                                      yscrollcommand=sb4.set)
        self.table_view_box.pack(fill=tk.BOTH, expand=True)
        sb4.config(command=self.table_view_box.yview)

    def build_graph_canvas(self):
        self.fig_f, self.ax_f = plt.subplots(figsize=(6, 8))
        self.canvas_f = FigureCanvasTkAgg(self.fig_f, master=self.right_column)
        self.canvas_f.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig_f.canvas.mpl_connect('button_press_event', self.on_graph_clicked)

    # -------------------------------------------------------
    # GRAPH CLICK
    # -------------------------------------------------------
    def on_graph_clicked(self, event):
        if event.xdata is None or event.ydata is None: return
        x0, y0 = event.xdata, event.ydata
        closest_node, closest_dist = None, float('inf')
        for node, (nx_val, ny_val) in self.node_positions.items():
            d = ((x0 - nx_val)**2 + (y0 - ny_val)**2)**0.5
            if d < closest_dist:
                closest_dist = d; closest_node = node
        if closest_dist <= 0.25 and closest_node:
            self.selected_node = closest_node
            if self.simulation_started:
                self.render_all_views()
            else:
                self.render_base_configuration_graph()
            return
        closest_edge, closest_edge_dist = None, float('inf')
        for u, v in self.G.edges():
            x1, y1 = self.node_positions[u]; x2, y2 = self.node_positions[v]
            dx, dy = x2 - x1, y2 - y1
            mag2 = dx*dx + dy*dy
            if mag2 == 0: continue
            t = max(0, min(1, ((x0-x1)*dx + (y0-y1)*dy) / mag2))
            d = ((x0 - x1 - t*dx)**2 + (y0 - y1 - t*dy)**2)**0.5
            if d < closest_edge_dist:
                closest_edge_dist = d; closest_edge = tuple(sorted((u, v)))
        if closest_edge_dist <= 0.15 and closest_edge:
            self.selected_edge = closest_edge
            if self.simulation_started:
                self.render_all_views()
            else:
                self.render_base_configuration_graph()

    # -------------------------------------------------------
    # BASE CONFIG GRAPH
    # -------------------------------------------------------
    def render_base_configuration_graph(self):
        self.ax_f.clear()
        nc = ['#1e3799' if n == self.selected_node else '#dcdde1' for n in sorted(self.G.nodes())]
        for u, v in self.G.edges():
            et = tuple(sorted((u, v)))
            c = '#a29bfe' if et == self.selected_edge else '#2c3e50'
            w = 6.0 if et == self.selected_edge else 1.5
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color=c, width=w, ax=self.ax_f)
        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=nc, node_size=800, edgecolors='#2c3e50', ax=self.ax_f)
        for name, (x, y) in self.node_positions.items():
            fc = 'white' if name == self.selected_node else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=12, fontweight='bold', ha='center', va='center', color=fc)
        el = {(u, v): f"bw:{d['bandwidth']}\ncost:{d['cost']}\n({d['delay']}ms)" for u, v, d in self.G.edges(data=True)}
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=el, font_size=9, font_weight='bold', ax=self.ax_f)
        self.ax_f.set_title("OSPF Topology — Configuration Mode  |  HMAC-SHA256 armed", fontsize=11, fontweight='bold', color="#2c3e50")
        self.ax_f.axis('off')
        self.canvas_f.draw()
        self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
        self.delay_change_combo.config(state="disabled")
        self.cost_change_combo.config(state="disabled")

    # -------------------------------------------------------
    # RUNTIME PANELS
    # -------------------------------------------------------
    def update_text_panels_data(self):
        target = self.selected_node
        T = self.current_time_ms
        state = self.timeline_states[T]

        # Link controls
        if self.selected_edge is None:
            self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
            self.delay_change_combo.config(state="disabled")
            self.cost_change_combo.config(state="disabled")
        else:
            u, v = self.selected_edge
            self.delay_change_combo.config(state="readonly")
            self.cost_change_combo.config(state="readonly")
            self.delay_change_combo.set(str(state["get_delay_func"](u, v, T)))
            self.cost_change_combo.set(str(state["get_cost_func"](u, v, T)))
            if self.selected_edge in state['broken_links']:
                self.link_toggle_btn.config(text=f"Enable Link {u}-{v}", state="normal", bg="#27ae60", fg="white")
            else:
                self.link_toggle_btn.config(text=f"Disable Link {u}-{v}", state="normal", bg="#c0392b", fg="white")

        # Convergence indicator
        if state["is_true_converged"]:
            self.convergence_indicator_lbl.config(
                text=f"CONVERGED & STABLE  [t={state['true_convergence_time']}ms]", bg="#d4edda", fg="#155724")
        elif state["is_protocol_converged"]:
            self.convergence_indicator_lbl.config(text="Stable but Inaccurate", bg="#fff3cd", fg="#856404")
        else:
            self.convergence_indicator_lbl.config(text="Syncing...", bg="#ffeaa7", fg="#d35400")

        # Build local topology from LSDB
        known = state['lsdb'][target]
        local_G = nx.Graph()
        local_G.add_node(target)
        for adv_node, lsa in known.items():
            for nbr, cost in lsa['neighbors'].items():
                local_G.add_edge(adv_node, nbr, weight=cost)

        lengths, paths = {}, {}
        try:
            lengths = nx.single_source_dijkstra_path_length(local_G, target, weight='weight')
            paths   = nx.single_source_dijkstra_path(local_G, target, weight='weight')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        # Labels
        self.packet_header_lbl.config(text=f"LSA Packet Data: Router {target}")
        self.local_log_header_lbl.config(text=f"Local Port Log for Router {target}:")
        self.table_header_lbl.config(text=f"Routing Table ({T}ms snapshot): Router {target}")

        # LSA packet view
        self.lsa_view_box.delete('1.0', tk.END)
        if target in known:
            lsa = known[target]
            tag_short = f"...{lsa.get('hmac','N/A')[-16:]}"
            self.lsa_view_box.insert(tk.END, f"Source:     Router_{target}\n")
            self.lsa_view_box.insert(tk.END, f"Seq Num:    {lsa['sequence_num']}\n")
            self.lsa_view_box.insert(tk.END, f"TTL:        {lsa['ttl']}\n")
            self.lsa_view_box.insert(tk.END, f"HMAC-SHA256: {tag_short}\n")
            costs_str = ", ".join(f"{k}(cost={v})" for k, v in lsa['neighbors'].items()) or "None"
            self.lsa_view_box.insert(tk.END, f"Neighbors:  {costs_str}")
        else:
            self.lsa_view_box.insert(tk.END, f"Router_{target}: DOWN — no LSA generated yet.")

        # Local port log
        self.local_router_log_box.config(state=tk.NORMAL)
        self.local_router_log_box.delete('1.0', tk.END)
        found = False
        for log_t, text, tag in self.router_events[target]:
            if log_t <= T:
                found = True
                self.local_router_log_box.insert(tk.END, f"[{log_t}ms] {text}\n", tag)
        if not found:
            self.local_router_log_box.insert(tk.END, "No events recorded yet.")
        self.local_router_log_box.config(state=tk.DISABLED)
        self.local_router_log_box.see(tk.END)

        # Routing table
        self.table_view_box.delete('1.0', tk.END)
        all_dests = sorted(n for n in local_G.nodes() if n != target)
        if not all_dests:
            self.table_view_box.insert(tk.END, "(No routes — no LSAs learned yet)\n")
        else:
            hdr = f"{'Destination':<14}  {'Cost':<6}  {'Next Hop':<12}  {'Path'}\n"
            self.table_view_box.insert(tk.END, hdr)
            self.table_view_box.insert(tk.END, "-" * 70 + "\n")
            for dest in all_dests:
                if dest in paths:
                    cost    = lengths[dest]
                    pv      = paths[dest]
                    nh      = pv[1] if len(pv) > 1 else dest
                    atk_flag = "  *** VIA ATTACK NODE ***" if "ATTACK" in pv else ""
                    self.table_view_box.insert(tk.END,
                        f"{'Rtr ' + dest:<14}  {cost:<6}  {'Rtr ' + nh:<12}  {' -> '.join(pv)}{atk_flag}\n")
                else:
                    self.table_view_box.insert(tk.END,
                        f"{'Rtr ' + dest:<14}  {'N/A':<6}  {'N/A':<12}  Unreachable\n")

    def next_timeline_step(self):
        step = int(self.step_combo.get())
        if self.current_time_ms < self.max_sim_time:
            self.current_time_ms = min(self.max_sim_time, self.current_time_ms + step)
            self.render_all_views()

    def prev_timeline_step(self):
        step = int(self.step_combo.get())
        if self.current_time_ms > 0:
            self.current_time_ms = max(0, self.current_time_ms - step)
            self.render_all_views()

    def render_all_views(self):
        self.update_text_panels_data()
        self.render_flooding_state_view()

    # -------------------------------------------------------
    # GRAPH RENDER
    # -------------------------------------------------------
    def render_flooding_state_view(self):
        self.ax_f.clear()
        T = self.current_time_ms
        state = self.timeline_states[T]

        # Global log
        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        for e in self.logs_database:
            if e["time"] <= T:
                self.flood_log.insert(tk.END, f"[{e['time']}ms] {e['text']}\n", e["type"])
        self.flood_log.config(state=tk.DISABLED)
        self.flood_log.see(tk.END)

        # Convergence log
        self.convergence_log_box.config(state=tk.NORMAL)
        self.convergence_log_box.delete('1.0', tk.END)
        found_metrics = False
        for item in self.convergence_metrics_database:
            if item["time"] <= T:
                found_metrics = True
                self.convergence_log_box.insert(tk.END, f"[{item['time']}ms] {item['text']}\n", item["type"])
        if not found_metrics:
            self.convergence_log_box.insert(tk.END, "No convergence events yet.")
        self.convergence_log_box.config(state=tk.DISABLED)
        self.convergence_log_box.see(tk.END)

        # LSDB matrix
        self.flood_matrix_text.delete('1.0', tk.END)
        self.flood_matrix_text.insert(tk.END, f"{'Node':<6} | LSDB contents\n{'-'*40}\n")
        for node, d in sorted(state['lsdb'].items()):
            self.flood_matrix_text.insert(tk.END, f"  {node:<4} | {{{', '.join(sorted(d.keys()))}}}\n")

        # Node colours
        total = len(self.G.nodes())
        nc = []
        for n in sorted(self.G.nodes()):
            if n == self.selected_node:   nc.append('#1e3799')
            elif len(state['lsdb'][n]) == total: nc.append('#2ecc71')
            elif len(state['lsdb'][n]) > 0:      nc.append('#e84118')
            else:                                  nc.append('#dcdde1')

        tx_edges, edge_color_map = set(), {}
        for u, v, ts, te, pt in state['active_links']:
            et = tuple(sorted((u, v)))
            tx_edges.add(et)
            edge_color_map[et] = '#00b894' if pt == "HELLO_ARRIVE" else '#f1c40f'

        for u, v in self.G.edges():
            et = tuple(sorted((u, v)))
            broken = et in state['broken_links']
            active = et in tx_edges
            selected = (et == self.selected_edge)
            if broken:
                if state['adj_states'][u][v] == "DOWN" or state['adj_states'][v][u] == "DOWN":
                    col, sty, wid = '#b2bec3', 'dotted', 2.0
                else:
                    col, sty, wid = '#e67e22', 'dashed', 3.5
            else:
                col = edge_color_map[et] if active else '#2c3e50'
                wid = 5.0 if active else 1.5
                sty = 'solid'
            if selected:
                nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u,v)],
                                       edge_color='#a29bfe', width=8.0, alpha=0.6, ax=self.ax_f)
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u,v)],
                                   edge_color=col, width=wid, style=sty, ax=self.ax_f)

        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=nc, node_size=800, edgecolors='#2c3e50', ax=self.ax_f)
        for name, (x, y) in self.node_positions.items():
            fc = 'white' if name == self.selected_node or len(state['lsdb'][name]) > 0 else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=12, fontweight='bold', ha='center', va='center', color=fc)

        el = {}
        for u, v, d in self.G.edges(data=True):
            et = tuple(sorted((u, v)))
            if et in state['broken_links']:
                status = "TIMEOUT" if (state['adj_states'][u][v]=="DOWN" or state['adj_states'][v][u]=="DOWN") else "HOLDING"
            else:
                status = f"cost:{state['get_cost_func'](u,v,T)}"
            delay = state['get_delay_func'](u, v, T)
            bw = self.original_edges_data.get(et, {}).get('bandwidth', '')
            el[(u, v)] = f"{status}\nbw:{bw}\n({delay}ms)"
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=el, font_size=9, font_weight='bold', ax=self.ax_f)

        if self.attack_injected and self.attack_inject_time is not None and T >= self.attack_inject_time:
            self.ax_f.set_title(
                f"OSPF Clock: {T}ms  |  ATTACK LSA @ {self.attack_inject_time}ms — BLOCKED BY HMAC-SHA256",
                fontsize=10, fontweight='bold', color="#c0392b")
        else:
            self.ax_f.set_title(f"OSPF Clock: {T}ms  |  HMAC-SHA256 Active", fontsize=11, fontweight='bold', color="#155724")
        self.ax_f.axis('off')
        self.canvas_f.draw()

if __name__ == '__main__':
    window_root = tk.Tk()
    application = OSPFAsynchronousWorkspaceDashboard(window_root)
    window_root.mainloop()