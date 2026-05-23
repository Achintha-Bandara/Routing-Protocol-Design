import tkinter as tk
from tkinter import ttk
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import json
import os
import glob
import math
import hmac
import hashlib
import secrets

def format_time(ms_total):
    if ms_total < 0: return "00:00:00:000"
    seconds, milliseconds = divmod(int(ms_total), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{milliseconds:03d}"

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


class AOSPFAsynchronousWorkspaceDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("AOSPF Unified Engine — HMAC-SHA256 Secured")
        self.root.geometry("1600x980")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # AOSPF Protocol Timer Configurations (in milliseconds)
        self.hello_interval = 3000
        self.dead_interval = 10000

        # Composite Cost Formula Parameters (Log-Bandwidth Model)
        self.w1 = 10.0
        self.w2 = 1.0
        self.L_max = 50.0
        self.BW_max = 1000.0

        # Persistent Global Convergence Database Metrics Buffer
        self.convergence_metrics_database = []

        self.G = nx.Graph()
        self.node_positions = {}
        self.original_edges_data = {}
        self.edges_definition = []
        self.selected_node = 'A'

        # Lifecycle State Trackers (initialised before setup_ui so reset_simulation is safe)
        self.simulation_started = False
        self.current_time_ms = 0
        self.simulation_running = False
        self.after_id = None
        self.selected_edge = None
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []
        self.node_processing_delay = 3
        self.attack_injected = False
        self.attack_inject_time = None

        # Build UI first (topology combo lives here)
        self.setup_ui()

        # Discover available topology files and populate combo
        self._populate_topology_combo()

        # Load whichever topology is selected by default
        self._load_topology(self.topology_combo.get())

        # Initial render
        self.reset_simulation()

    # -------------------------------------------------------
    # TOPOLOGY DISCOVERY & LOADING
    # -------------------------------------------------------
    def _populate_topology_combo(self):
        """Scan script directory for topology_*.json files and fill the combo."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pattern = os.path.join(script_dir, 'topology_*.json')
        found = sorted([os.path.basename(p) for p in glob.glob(pattern)])
        if not found:
            found = ['topology_5.json']   # fallback label even if missing
        self.topology_combo['values'] = found
        self.topology_combo.set(found[0])

    def _load_topology(self, filename: str):
        """Load network topology from *filename* (basename) in the script directory."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        topology_path = os.path.join(script_dir, filename)

        if not os.path.exists(topology_path):
            tk.messagebox.showerror(
                "Topology Not Found",
                f"Could not find:\n{topology_path}\n\nPlease ensure the file exists."
            )
            return

        with open(topology_path, 'r') as f:
            data = json.load(f)

        # Build node positions from file
        self.node_positions = {}
        for node in data.get('nodes', []):
            self.node_positions[node['id']] = (node['x'], node['y'])

        # Build edge list and graph from file
        self.edges_definition = []
        self.original_edges_data = {}
        self.G.clear()

        REFERENCE_BW_MBPS = 1000

        def parse_bandwidth_mbps(bw_str):
            import re
            m = re.match(r'(\d+(?:\.\d+)?)(Gbps|Mbps|Kbps)', bw_str, re.IGNORECASE)
            if not m:
                return 100.0
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit == 'gbps':   return val * 1000
            if unit == 'mbps':   return val
            if unit == 'kbps':   return val / 1000
            return val

        for edge in data.get('edges', []):
            u = edge['from']
            v = edge['to']
            bw_str = edge.get('bandwidth', '100Mbps')
            delay  = edge.get('delay', 10)
            bw_mbps = parse_bandwidth_mbps(bw_str)
            cost = max(1, math.ceil(REFERENCE_BW_MBPS / bw_mbps))
            self.edges_definition.append((u, v, cost, delay))
            self.G.add_edge(u, v, cost=cost, bandwidth=bw_str, delay=delay)
            self.original_edges_data[tuple(sorted((u, v)))] = {
                'cost': cost, 'bandwidth': bw_str, 'bandwidth_mbps': bw_mbps, 'delay': delay
            }

        all_nodes = sorted(self.node_positions.keys())
        self.selected_node = all_nodes[0] if all_nodes else 'A'

    def on_topology_change(self, event=None):
        """Called when the user picks a different topology from the combo."""
        if self.simulation_started:
            return   # combo is disabled during simulation, but guard anyway
        self._load_topology(self.topology_combo.get())
        self.reset_simulation()

    def on_closing(self):
        plt.close('all')
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    # -------------------------------------------------------
    # SIMULATION LIFECYCLE CONTROLLERS
    # -------------------------------------------------------
    def start_simulation(self):
        self.hello_interval = int(self.hello_combo.get())
        self.dead_interval = self.hello_interval * 4
        self.w1 = float(self.w1_combo.get())
        self.w2 = float(self.w2_combo.get())
        self.current_time_ms = 0
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []
        self.selected_edge = None
        self.attack_injected = False
        self.attack_inject_time = None
        self.convergence_metrics_database = []

        self.sim_generator = self.run_continuous_event_simulation()
        next(self.sim_generator)
        self.simulation_started = True
        self.simulation_running = True

        self.topology_combo.config(state="disabled")
        self.hello_combo.config(state="disabled")
        self.w1_combo.config(state="disabled")
        self.w2_combo.config(state="disabled")
        self.start_btn.config(text="⏸ Pause", command=self.toggle_pause)
        self.attack_btn.config(state="normal")
        self.prev_btn.config(state="normal")
        self.next_btn.config(state="normal")
        self.sync_btn.config(state="normal")
        self.reset_btn.config(state="normal")

        self.render_all_views()
        self.auto_step()

    def toggle_pause(self):
        if not self.simulation_started: return
        self.simulation_running = not self.simulation_running
        if self.simulation_running:
            self.start_btn.config(text="⏸ Pause")
            self.auto_step()
        else:
            self.start_btn.config(text="▶ Play")

    def auto_step(self):
        if not self.simulation_running:
            return
        step = int(self.step_combo.get())
        target = self.current_time_ms + step
        while len(self.timeline_states) <= target:
            next(self.sim_generator)
        self.current_time_ms = target
        self.render_all_views()
        self.after_id = self.root.after(50, self.auto_step)

    def reset_simulation(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.simulation_started = False
        self.simulation_running = False
        self.current_time_ms = 0
        self.selected_edge = None
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes = []
        self.attack_injected = False
        self.attack_inject_time = None
        self.convergence_metrics_database = []

        self.topology_combo.config(state="readonly")
        self.hello_combo.config(state="readonly")
        self.w1_combo.config(state="readonly")
        self.w2_combo.config(state="readonly")
        self.start_btn.config(text="Start Simulation 🚀", command=self.start_simulation, state="normal")
        self.attack_btn.config(state="disabled")
        self.prev_btn.config(state="disabled")
        self.next_btn.config(state="disabled")
        self.sync_btn.config(state="disabled")
        self.reset_btn.config(state="normal")

        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        self.flood_log.insert(tk.END, "SYSTEM IDLE — Select topology and configure metrics above, then click 'Start Simulation' to begin.")
        self.flood_log.config(state=tk.DISABLED)

        self.convergence_log_box.config(state=tk.NORMAL)
        self.convergence_log_box.delete('1.0', tk.END)
        self.convergence_log_box.insert(tk.END, "Awaiting simulation initialization to compile metrics data logs...")
        self.convergence_log_box.config(state=tk.DISABLED)

        self.flood_matrix_text.delete('1.0', tk.END)
        self.table_view_box.delete('1.0', tk.END)
        self.lsa_view_box.delete('1.0', tk.END)

        self.local_router_log_box.config(state=tk.NORMAL)
        self.local_router_log_box.delete('1.0', tk.END)
        self.local_router_log_box.insert(tk.END, "Adjacency links offline. Run simulation to discover ports.")
        self.local_router_log_box.config(state=tk.DISABLED)

        self.convergence_indicator_lbl.config(text="Simulation Not Started", bg="#dcdde1", fg="#2c3e50")
        self.hmac_banner.config(text="HMAC-SHA256 security layer active — all LSAs signed on transmit", bg="#2c3e50", fg="#dfe6e9")

        self.render_base_configuration_graph()

    def inject_fake_lsa(self):
        if not self.simulation_started:
            return
        self.attack_injected = True
        self.attack_inject_time = self.current_time_ms
        self._rebuild_history()
        self.render_all_views()
        self.hmac_banner.config(
            text=f"ATTACK LSA injected at t={format_time(self.attack_inject_time)} — HMAC verification BLOCKED it (see Global Log)",
            bg="#c0392b", fg="white"
        )

    def toggle_selected_link(self):
        if self.selected_edge and self.simulation_started:
            self.link_toggles.append((self.selected_edge, self.current_time_ms))
            self._rebuild_history()
            self.render_all_views()

    def apply_runtime_delay_change(self, event=None):
        if self.selected_edge and self.simulation_started:
            new_delay = int(self.delay_change_combo.get())
            self.delay_changes.append((self.selected_edge, new_delay, self.current_time_ms))
            u, v = self.selected_edge
            self.logs_database.append({
                "time": self.current_time_ms,
                "text": f"🔧 PROPAGATION MODIFICATION: Latency delay on interface link {u}-{v} modified to {new_delay}ms at runtime.",
                "routers": [u, v], "type": "process"
            })
            self._rebuild_history()
            self.render_all_views()

    def skip_to_synchronize(self):
        if self.simulation_started:
            t = self.current_time_ms
            if self.timeline_states[t]["is_true_converged"]:
                while self.timeline_states[t]["is_true_converged"]:
                    t += 1
                    while len(self.timeline_states) <= t: next(self.sim_generator)
            while True:
                while len(self.timeline_states) <= t: next(self.sim_generator)
                if self.timeline_states[t]["is_true_converged"]:
                    self.current_time_ms = t
                    break
                t += 1
            self.render_all_views()

    # -------------------------------------------------------
    # DISCRETE SIMULATION ENGINE (WITH HMAC)
    # -------------------------------------------------------
    def _rebuild_history(self):
        self.sim_generator = self.run_continuous_event_simulation()
        self.timeline_states = {}
        for _ in range(self.current_time_ms + 1):
            next(self.sim_generator)

    def run_continuous_event_simulation(self):
        nodes = sorted(list(self.G.nodes()))
        total_nodes_count = len(nodes)

        current_lsdb = {n: {} for n in nodes}
        adj_states = {n: {nbr: "DOWN" for nbr in self.G.neighbors(n)} for n in nodes}
        last_hello_time = {n: {nbr: 0 for nbr in self.G.neighbors(n)} for n in nodes}
        lsa_seq = {n: 1 for n in nodes}
        lsa_triggered = {n: False for n in nodes}
        broken_links = set()

        event_queue = []
        self.logs_database = []
        self.router_events = {n: [] for n in nodes}

        pending_failure_tracks = []
        pending_cost_tracks = []

        advertised_costs = {n: {nbr: self.original_edges_data[tuple(sorted((n, nbr)))]['cost'] for nbr in self.G.neighbors(n)} for n in nodes}

        def get_current_delay(u_node, v_node, eval_time):
            e_tuple = tuple(sorted((u_node, v_node)))
            base_delay = self.original_edges_data[e_tuple]['delay']
            for mod_edge, mod_delay, timestamp in self.delay_changes:
                if mod_edge == e_tuple and timestamp <= eval_time:
                    base_delay = mod_delay
            return base_delay

        def get_link_bandwidth(u_node, v_node):
            e_tuple = tuple(sorted((u_node, v_node)))
            return self.original_edges_data[e_tuple]['bandwidth_mbps']

        self.logs_database.append({
            "time": 0,
            "text": (f"[BOOT] All routers initialised. HELLO interval={self.hello_interval}ms. "
                     f"HMAC-SHA256 signing enabled (shared key ...{OSPF_HMAC_KEY.hex()[-8:]})."),
            "routers": list(nodes), "type": "init"
        })
        for n in nodes:
            event_queue.append((0, "HELLO_SEND", (n,)))

        if self.attack_injected and self.attack_inject_time is not None:
            event_queue.append((self.attack_inject_time, "FAKE_LSA_INJECT", ()))

        self.timeline_states = {}
        last_logged_state = "RED"
        initial_sync_logged = len([x for x in self.convergence_metrics_database if x["type"] == "INITIAL"]) > 0
        last_protocol_instability = 0
        last_true_instability = 0

        current_time = 0
        while True:
            active_protocol_disruption = False

            for edge, toggle_time in self.link_toggles:
                if toggle_time == current_time:
                    u, v = edge
                    if edge in broken_links:
                        broken_links.remove(edge)
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"🛠️ LINK RESTORED: Physical connection established between Router {u} and Router {v}. Awaiting periodic HELLO discovery.",
                            "routers": [u, v], "type": "process"
                        })
                        self.router_events[u].append((current_time, f"Physical link layer to Router {v} restored. Interface status UP, waiting for background periodic HELLO timer.", "init"))
                        self.router_events[v].append((current_time, f"Physical link layer to Router {u} restored. Interface status UP, waiting for background periodic HELLO timer.", "init"))
                    else:
                        broken_links.add(edge)
                        pending_failure_tracks.append({"edge": edge, "t_fail": current_time, "t_timeout": None})
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"💥 LINK SEVERED: Cable cut between Router {u} and Router {v}. Dropping packets; awaiting interface Hello keepalive timeouts.",
                            "routers": [u, v], "type": "dropped"
                        })
                        self.router_events[u].append((current_time, f"Link interface route to Router {v} broken. Packet dropping active, waiting for Hello dead timer to trip.", "dropped"))
                        self.router_events[v].append((current_time, f"Link interface route to Router {u} broken. Packet dropping active, waiting for Hello dead timer to trip.", "dropped"))

            for u in nodes:
                for nbr in self.G.neighbors(u):
                    if adj_states[u][nbr] in ["INIT", "2WAY"]:
                        if current_time - last_hello_time[u][nbr] >= self.dead_interval:
                            adj_states[u][nbr] = "DOWN"
                            active_protocol_disruption = True
                            target_edge = tuple(sorted((u, nbr)))
                            for item in pending_failure_tracks:
                                if item["edge"] == target_edge and item["t_timeout"] is None:
                                    item["t_timeout"] = current_time
                            self.logs_database.append({
                                "time": current_time,
                                "text": f"⏳ DEAD TIMER EXPIRED: Router {u} identified path failure to Router {nbr} (Missed keepalives for {self.dead_interval}ms). Adjacency destroyed.",
                                "routers": [u, nbr], "type": "dropped"
                            })
                            self.router_events[u].append((current_time, f"Dead Timer Timeout for Router {nbr} ({self.dead_interval}ms passed). Tearing down adjacency interface.", "dropped"))
                            lsa_seq[u] += 1
                            active_nbrs = {k: advertised_costs[u][k] for k in self.G.neighbors(u) if adj_states[u][k] == "2WAY"}
                            lsa_payload = sign_lsa({
                                "router_id": u, "sequence_num": lsa_seq[u], "ttl": 64, "neighbors": active_nbrs
                            })
                            current_lsdb[u][u] = lsa_payload
                            self.router_events[u].append((current_time, f"Generated updated topology Router-LSA (Seq: {lsa_seq[u]}) isolating dead interface.", "db_update"))
                            for flooded_nbr in self.G.neighbors(u):
                                if adj_states[u][flooded_nbr] == "2WAY":
                                    link_prop_delay = get_current_delay(u, flooded_nbr, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (u, flooded_nbr, lsa_payload, link_prop_delay)))
                                    self.router_events[u].append((current_time, f"Flooded corrective update LSA forward to neighbor Router {flooded_nbr}.", "sent"))

            event_queue.sort(key=lambda x: x[0])

            while event_queue and event_queue[0][0] == current_time:
                t_curr, ev_type, data = event_queue.pop(0)

                if ev_type == "HELLO_SEND":
                    router = data[0]
                    active_neighbors = [k for k, v in adj_states[router].items() if v in ["INIT", "2WAY"]]
                    if current_time > 0:
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"Periodic keepalive AOSPF HELLO broadcast sent from Router {router} out of interfaces.",
                            "routers": [router], "type": "hello_tx"
                        })
                        self.router_events[router].append((current_time, "Sent periodic AOSPF HELLO keepalive broadcast window frame out of interfaces.", "hello_tx"))
                    for nbr in self.G.neighbors(router):
                        delay = get_current_delay(router, nbr, current_time)
                        event_queue.append((current_time + delay, "HELLO_ARRIVE", (router, nbr, list(active_neighbors), delay, current_time)))
                    event_queue.append((current_time + self.hello_interval, "HELLO_SEND", (router,)))

                elif ev_type == "HELLO_ARRIVE":
                    sender, receiver, sender_neighbor_list, link_delay, sent_time = data
                    if tuple(sorted((sender, receiver))) in broken_links:
                        continue
                    last_hello_time[receiver][sender] = current_time

                    measured_delay = current_time - sent_time
                    link_bw = get_link_bandwidth(receiver, sender)
                    bw_ratio = max(link_bw / self.BW_max, 1e-9)
                    temp_cost = self.w1 * (measured_delay / self.L_max) + self.w2 * (-math.log(bw_ratio))
                    temp_cost = max(1, math.ceil(temp_cost))
                    old_advertised_cost = advertised_costs[receiver][sender]

                    comparison_msg = (
                        f"Cost Evaluation for link to {sender}: Measured Delay = {measured_delay}ms -> Temp Cost = {temp_cost} "
                        f"(w1*(L/Lmax) + w2*(-log(BW/BWmax)) = {self.w1}*({measured_delay}/{self.L_max}) + {self.w2}*(-log({link_bw}/{self.BW_max}))). "
                        f"Previous Advertised Cost = {old_advertised_cost}."
                    )
                    self.router_events[receiver].append((current_time, comparison_msg, "hello_rx"))

                    if receiver in sender_neighbor_list:
                        if adj_states[receiver][sender] != "2WAY":
                            adj_states[receiver][sender] = "2WAY"
                            active_protocol_disruption = True
                            advertised_costs[receiver][sender] = temp_cost
                            self.router_events[receiver].append((current_time, f"Received reflective Hello from Router {sender}. Handshake complete: 2-WAY achieved.", "hello_rx"))
                            lsa_triggered[receiver] = True
                            lsa_seq[receiver] += 1
                            active_nbrs = {k: advertised_costs[receiver][k] for k in self.G.neighbors(receiver) if adj_states[receiver][k] == "2WAY"}
                            lsa_payload = sign_lsa({
                                "router_id": receiver, "sequence_num": lsa_seq[receiver], "ttl": 64, "neighbors": active_nbrs
                            })
                            current_lsdb[receiver][receiver] = lsa_payload
                            self.router_events[receiver].append((current_time, f"Triggered optimization LSA metrics re-generation pass (Seq: {lsa_seq[receiver]}).", "db_update"))
                            for nbr in self.G.neighbors(receiver):
                                if adj_states[receiver][nbr] == "2WAY":
                                    link_prop_delay = get_current_delay(receiver, nbr, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (receiver, nbr, lsa_payload, link_prop_delay)))
                                    self.router_events[receiver].append((current_time, f"Flooded updated database LSA map forward onto route to Router {nbr}.", "sent"))
                            for lsa_owner, lsa_entry in current_lsdb[receiver].items():
                                if lsa_owner != receiver:
                                    link_prop_delay = get_current_delay(receiver, sender, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (receiver, sender, lsa_entry, link_prop_delay)))
                                    self.router_events[receiver].append((current_time, f"DB Exchange: Sent cached LSA [Router_{lsa_owner}] to new neighbor Router {sender}.", "sent"))
                        else:
                            self.logs_database.append({
                                "time": current_time,
                                "text": f"Routine keepalive HELLO received at Router {receiver} from neighbor Router {sender} (Dead timer refreshed).",
                                "routers": [sender, receiver], "type": "hello_rx"
                            })
                            if temp_cost >= 1.4 * old_advertised_cost or temp_cost <= 0.6 * old_advertised_cost:
                                active_protocol_disruption = True
                                advertised_costs[receiver][sender] = temp_cost
                                edge_key = tuple(sorted((sender, receiver)))
                                t_change = 0
                                for mod_edge, _, timestamp in self.delay_changes:
                                    if mod_edge == edge_key and timestamp <= current_time:
                                        t_change = max(t_change, timestamp)
                                pending_cost_tracks.append({
                                    "edge": edge_key, "t_change": t_change, "t_detection": current_time
                                })
                                change_direction = "increased" if temp_cost >= 1.4 * old_advertised_cost else "decreased"
                                self.logs_database.append({
                                    "time": current_time,
                                    "text": f"📈 COST METRIC CHANGE: Dynamic metric cost to neighbor Router {sender} {change_direction} by >= 40% (New Cost: {temp_cost}, Old: {old_advertised_cost}). Dispatching triggered update LSA.",
                                    "routers": [receiver, sender], "type": "process"
                                })
                                self.router_events[receiver].append((current_time, f"Dynamic cost to Router {sender} hit trigger threshold (+/-40%). Issuing active link update LSA (Seq: {lsa_seq[receiver]+1}).", "db_update"))
                                lsa_seq[receiver] += 1
                                active_nbrs = {k: advertised_costs[receiver][k] for k in self.G.neighbors(receiver) if adj_states[receiver][k] == "2WAY"}
                                lsa_payload = sign_lsa({
                                    "router_id": receiver, "sequence_num": lsa_seq[receiver], "ttl": 64, "neighbors": active_nbrs
                                })
                                current_lsdb[receiver][receiver] = lsa_payload
                                for nbr in self.G.neighbors(receiver):
                                    if adj_states[receiver][nbr] == "2WAY":
                                        link_prop_delay = get_current_delay(receiver, nbr, current_time)
                                        event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (receiver, nbr, lsa_payload, link_prop_delay)))
                    else:
                        if adj_states[receiver][sender] == "DOWN":
                            adj_states[receiver][sender] = "INIT"
                            active_protocol_disruption = True
                            self.router_events[receiver].append((current_time, f"Router ID missing from packet. Moved Router {sender} to INIT state. Scheduling immediate reactive HELLO response.", "process"))
                            t_resp_send = current_time + self.node_processing_delay
                            t_resp_arrive = t_resp_send + link_delay
                            reactive_neighbors = [k for k, v in adj_states[receiver].items() if v in ["INIT", "2WAY"]]
                            event_queue.append((t_resp_arrive, "HELLO_ARRIVE", (receiver, sender, list(reactive_neighbors), link_delay, current_time)))

                elif ev_type == "LSA_ARRIVE":
                    sender, receiver, incoming_payload, link_delay = data
                    if tuple(sorted((sender, receiver))) in broken_links:
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

                    cached_seq = current_lsdb[receiver].get(owner, {}).get("sequence_num", 0)
                    if incoming_payload["sequence_num"] > cached_seq:
                        t_process_finish = current_time + self.node_processing_delay
                        event_queue.append((t_process_finish, "LSA_PROCESS", (receiver, incoming_payload, sender)))
                        self.router_events[receiver].append((current_time, f"LSA is newer than cached sequence ({cached_seq}). Scheduling local port LSA flood processing in +{self.node_processing_delay}ms.", "process"))
                    else:
                        self.router_events[receiver].append((current_time, f"Dropped duplicate LSA [Origin: Router {owner}] (Suppression active).", "dropped"))

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

                elif ev_type == "LSA_PROCESS":
                    router, incoming_payload, arrival_port = data
                    active_protocol_disruption = True
                    owner = incoming_payload["router_id"]
                    cached_seq = current_lsdb[router].get(owner, {}).get("sequence_num", 0)
                    if incoming_payload["sequence_num"] > cached_seq:
                        current_lsdb[router][owner] = incoming_payload
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"Router {router} updates local LSDB database maps for [Router_{owner}].",
                            "routers": [router], "type": "db_update"
                        })
                        self.router_events[router].append((current_time, f"Stored updated [Router_{owner}] advertisement map into local LSDB database.", "db_update"))
                        for nbr in self.G.neighbors(router):
                            if nbr != arrival_port and adj_states[router][nbr] == "2WAY":
                                link_prop_delay = get_current_delay(router, nbr, current_time)
                                event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (router, nbr, incoming_payload, link_prop_delay)))
                                self.router_events[router].append((current_time, f"Sent LSA forward [Origin: Router {owner}] flooded out to neighbor Router {nbr}.", "sent"))

            operational_nodes = [n for n in nodes if any(status == "2WAY" for status in adj_states[n].values())]
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
                edge_tuple = tuple(sorted((u, v)))
                is_broken = edge_tuple in broken_links
                for n in nodes:
                    u_has_v = v in current_lsdb[n].get(u, {}).get("neighbors", {})
                    v_has_u = u in current_lsdb[n].get(v, {}).get("neighbors", {})
                    if is_broken:
                        if u_has_v or v_has_u: is_physically_accurate = False; break
                    else:
                        if not (u_has_v and v_has_u): is_physically_accurate = False; break
                if not is_physically_accurate: break

            is_delay_cost_discrepancy = False
            for u_node, v_node in self.G.edges():
                edge_tuple = tuple(sorted((u_node, v_node)))
                if edge_tuple in broken_links:
                    continue
                l_delay = get_current_delay(u_node, v_node, current_time)
                link_bw = get_link_bandwidth(u_node, v_node)
                bw_ratio = max(link_bw / self.BW_max, 1e-9)
                true_cost = max(1, math.ceil(self.w1 * (l_delay / self.L_max) + self.w2 * (-math.log(bw_ratio))))
                old_u = advertised_costs[u_node][v_node]
                old_v = advertised_costs[v_node][u_node]
                if true_cost != old_u or true_cost != old_v:
                    if (true_cost >= 1.4 * old_u or true_cost <= 0.6 * old_u) or (true_cost >= 1.4 * old_v or true_cost <= 0.6 * old_v):
                        is_delay_cost_discrepancy = True; break

            has_pending_lsas = any(ev[1] in ["LSA_ARRIVE", "LSA_PROCESS"] for ev in event_queue)

            if active_protocol_disruption or has_pending_lsas or not is_synchronized:
                last_protocol_instability = current_time
            is_protocol_converged = (current_time > last_protocol_instability) and (len(operational_nodes) > 0)

            if active_protocol_disruption or has_pending_lsas or not is_synchronized or not is_physically_accurate or is_delay_cost_discrepancy:
                last_true_instability = current_time
            is_true_converged = (current_time > last_true_instability) and (len(operational_nodes) > 0)

            current_state_str = "RED"
            if is_true_converged:
                current_state_str = "GREEN"
            elif is_protocol_converged:
                current_state_str = "YELLOW_DELAY" if is_delay_cost_discrepancy else "YELLOW"

            if current_state_str != last_logged_state:
                if current_state_str == "GREEN":
                    self.logs_database.append({
                        "time": current_time,
                        "text": f"⭐ AOSPF NETWORK TOPOLOGY CONVERGENCE ACHIEVED! All local database maps are synchronized completely identical and accurate to physical wire states.",
                        "routers": list(nodes), "type": "converged"
                    })
                    if not initial_sync_logged:
                        initial_sync_logged = True
                        self.convergence_metrics_database.append({
                            "time": current_time, "type": "INITIAL",
                            "text": f"📌 [Initial Network Initialization Pass]\n• Time to Reach Initial Synchronization: {format_time(current_time)} from system boot frame.\n"
                        })
                    for item in list(pending_failure_tracks):
                        if item["t_timeout"] is not None:
                            t_fail = item["t_fail"]; t_timeout = item["t_timeout"]
                            duration_from_fail = current_time - t_fail
                            duration_from_timeout = current_time - t_timeout
                            u, v = item["edge"]
                            msg = (
                                f"⚡ [Link Failure Recovery Profile: Interrupted Interface Path {u} - {v}]\n"
                                f"  • Total Time to Synchronize After Physical Link Failure: {format_time(duration_from_fail)} (Disrupted at {format_time(t_fail)})\n"
                                f"  • Time to Synchronize After Fault Detection (Dead Timer Expiry): {format_time(duration_from_timeout)} (Alerted at {format_time(t_timeout)})\n"
                            )
                            if not any(x["text"] == msg and x["time"] == current_time for x in self.convergence_metrics_database):
                                self.convergence_metrics_database.append({"time": current_time, "type": "DISRUPTION", "text": msg})
                            pending_failure_tracks.remove(item)
                    for item in list(pending_cost_tracks):
                        t_change = item["t_change"]; t_detection = item["t_detection"]
                        duration_from_change = current_time - t_change
                        duration_from_detection = current_time - t_detection
                        u, v = item["edge"]
                        msg = (
                            f"📈 [Cost Metric Dynamic Shift Profile: Link {u} - {v}]\n"
                            f"  • Total Time to Synchronize After Physical Delay Alteration (Outside Sense): {format_time(duration_from_change)} (Altered at {format_time(t_change)})\n"
                            f"  • Time to Synchronize After Threshold Detection by Router: {format_time(duration_from_detection)} (Detected at {format_time(t_detection)})\n"
                        )
                        if not any(x["text"] == msg and x["time"] == current_time for x in self.convergence_metrics_database):
                            self.convergence_metrics_database.append({"time": current_time, "type": "DISRUPTION", "text": msg})
                        pending_cost_tracks.remove(item)
                elif current_state_str == "YELLOW_DELAY":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "AOSPF link delay cost discrepancy detected in outside sense (Awaiting Hello detection handshake).",
                        "routers": list(nodes), "type": "process"
                    })
                elif current_state_str == "YELLOW":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "AOSPF network state synchronized, but inaccurate to physical map (Topology discrepancy window active).",
                        "routers": list(nodes), "type": "process"
                    })
                last_logged_state = current_state_str

            active_tx = []
            for t_future, type_f, data_f in event_queue:
                if type_f in ["LSA_ARRIVE", "HELLO_ARRIVE"]:
                    s_f, r_f, *extra = data_f
                    d_f = extra[-1]
                    t_start = t_future - d_f
                    if t_start <= current_time < t_future and tuple(sorted((s_f, r_f))) not in broken_links:
                        active_tx.append((s_f, r_f, t_start, t_future, type_f))

            self.timeline_states[current_time] = {
                "lsdb": {n: {k: dict(v) for k, v in current_lsdb[n].items()} for n in nodes},
                "active_links": list(active_tx),
                "broken_links": set(broken_links),
                "adj_states": {n: dict(adj_states[n]) for n in nodes},
                "is_protocol_converged": is_protocol_converged,
                "is_true_converged": is_true_converged,
                "true_convergence_time": last_true_instability if is_true_converged else -1,
                "get_delay_func": get_current_delay,
                "get_bw_func": get_link_bandwidth,
                "advertised_costs": {n: dict(advertised_costs[n]) for n in nodes},
                "is_delay_cost_discrepancy": is_delay_cost_discrepancy
            }
            yield current_time
            current_time += 1

    # -------------------------------------------------------
    # UI Layout Construction
    # -------------------------------------------------------
    def setup_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)

        left_container = tk.Frame(self.root, width=630)
        left_container.grid(row=0, column=0, sticky="nswe")
        left_container.grid_propagate(False)
        left_container.grid_rowconfigure(0, weight=1)
        left_container.grid_columnconfigure(0, weight=1)

        self.left_canvas = tk.Canvas(left_container, highlightthickness=0)
        scrollbar = tk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=scrollbar.set)
        self.left_canvas.grid(row=0, column=0, sticky="nswe")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.left_column = tk.Frame(self.left_canvas, padx=10, pady=10)
        self.left_canvas.create_window((0, 0), window=self.left_column, anchor="nw")
        self.left_column.bind("<Configure>", self._on_left_column_configure)
        self.left_canvas.bind("<Configure>", self._on_left_canvas_configure)

        self.right_column = tk.Frame(self.root, padx=10, pady=10)
        self.right_column.grid(row=0, column=1, sticky="nswe")
        self.right_column.grid_rowconfigure(0, weight=1)
        self.right_column.grid_columnconfigure(0, weight=1)

        self.build_top_flooding_panel()
        self.build_bottom_inspector_panel()
        self.build_graph_canvas()

    def _on_left_column_configure(self, event=None):
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def _on_left_canvas_configure(self, event):
        self.left_canvas.itemconfig(self.left_canvas.find_withtag("all")[0], width=event.width)

    def build_top_flooding_panel(self):
        flood_frame = tk.LabelFrame(self.left_column, text=" 1. LSA Flooding & Security Panel ", font=("Helvetica", 11, "bold"), fg="#2c3e50", padx=8, pady=8)
        flood_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # ── Topology selector ──────────────────────────────────────────────
        topo_row = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        topo_row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(topo_row, text="Network Topology File:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.topology_combo = ttk.Combobox(topo_row, state="readonly", width=22)
        self.topology_combo.pack(side=tk.LEFT, padx=4)
        self.topology_combo.bind("<<ComboboxSelected>>", self.on_topology_change)
        # ──────────────────────────────────────────────────────────────────

        row1 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1, text="OSPF Hello Interval (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.hello_combo = ttk.Combobox(row1, values=["1000", "2000", "3000", "5000"], state="readonly", width=6)
        self.hello_combo.pack(side=tk.LEFT, padx=4)
        self.hello_combo.set("3000")
        self.start_btn = tk.Button(row1, text="Start Simulation", font=("Helvetica", 9, "bold"), command=self.start_simulation, bg="#27ae60", fg="white")
        self.start_btn.pack(side=tk.RIGHT, padx=4)

        row1b = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row1b.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1b, text="AOSPF Metrics — w1:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.w1_combo = ttk.Combobox(row1b, values=["0", "1", "2", "5", "10", "20", "50"], state="readonly", width=4)
        self.w1_combo.pack(side=tk.LEFT, padx=2)
        self.w1_combo.set("10")
        tk.Label(row1b, text="w2:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.w2_combo = ttk.Combobox(row1b, values=["0", "1", "2", "5", "10", "20", "50"], state="readonly", width=4)
        self.w2_combo.pack(side=tk.LEFT, padx=2)
        self.w2_combo.set("1")

        self.hmac_banner = tk.Label(flood_frame, text="HMAC-SHA256 security layer active — all LSAs signed on transmit", font=("Helvetica", 9, "bold"), bg="#2c3e50", fg="#dfe6e9", bd=1, relief=tk.SUNKEN, pady=3)
        self.hmac_banner.pack(fill=tk.X, pady=(0, 4))

        row2 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row2.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row2, text="Security Attack:", font=("Helvetica", 9, "bold"), fg="#c0392b").pack(side=tk.LEFT, padx=2)
        self.attack_btn = tk.Button(row2, text="Inject Fake LSA 💥", font=("Helvetica", 9, "bold"), command=self.inject_fake_lsa, state="disabled", bg="#c0392b", fg="white", activebackground="#a93226")
        self.attack_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=4)

        row3 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row3.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row3, text="Link Disruption:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.link_toggle_btn = tk.Button(row3, text="Select a Link on Map", font=("Helvetica", 9, "bold"), state="disabled", command=self.toggle_selected_link)
        self.link_toggle_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=4)

        row4 = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=4, pady=4)
        row4.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row4, text="Runtime Delay (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.delay_change_combo = ttk.Combobox(row4, values=["2","5","8","12","15","20","25","30","40","50"], state="disabled", width=8)
        self.delay_change_combo.pack(side=tk.RIGHT, padx=4)
        self.delay_change_combo.bind("<<ComboboxSelected>>", self.apply_runtime_delay_change)

        step_row = tk.Frame(flood_frame)
        step_row.pack(fill=tk.X, pady=2)
        tk.Label(step_row, text="Step Size (ms):", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.step_combo = ttk.Combobox(step_row, values=["5","10","50","100","1000"], state="readonly", width=8)
        self.step_combo.pack(side=tk.LEFT, padx=4)
        self.step_combo.set("100")

        nav_row = tk.Frame(flood_frame)
        nav_row.pack(fill=tk.X, pady=4)
        self.prev_btn = tk.Button(nav_row, text="◀ Prev", font=("Helvetica", 10, "bold"), command=self.prev_timeline_step, bg="#222f3e", fg="white")
        self.prev_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.next_btn = tk.Button(nav_row, text="Next ▶", font=("Helvetica", 10, "bold"), command=self.next_timeline_step, bg="#1e3799", fg="white")
        self.next_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=3)

        sc_row = tk.Frame(flood_frame)
        sc_row.pack(fill=tk.X, pady=2)
        self.sync_btn = tk.Button(sc_row, text="Skip to Convergence ⚡", font=("Helvetica", 9, "bold"), command=self.skip_to_synchronize, bg="#f39c12", fg="white")
        self.sync_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.reset_btn = tk.Button(sc_row, text="Reset Engine", font=("Helvetica", 9, "bold"), command=self.reset_simulation, bg="#7f8c8d", fg="white")
        self.reset_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        self.convergence_indicator_lbl = tk.Label(flood_frame, text="Simulation Not Started", font=("Helvetica", 10, "bold"), bg="#dcdde1", fg="#2c3e50", bd=1, relief=tk.SOLID, pady=3)
        self.convergence_indicator_lbl.pack(fill=tk.X, pady=4)

        tk.Label(flood_frame, text="LSDB Sync Matrix:", font=("Helvetica", 9, "bold"), fg="#34495e").pack(anchor=tk.W)
        self.flood_matrix_text = tk.Text(flood_frame, height=5, font=("Courier New", 9), bg="#f8f9fa", bd=1, relief=tk.SOLID)
        self.flood_matrix_text.pack(fill=tk.X)

        nb = ttk.Notebook(flood_frame)
        nb.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tab_global = tk.Frame(nb)
        tab_conv = tk.Frame(nb)
        nb.add(tab_global, text=" Global Commentary Log ")
        nb.add(tab_conv, text=" Convergence Log ")

        sb1 = tk.Scrollbar(tab_global)
        sb1.pack(side=tk.RIGHT, fill=tk.Y)
        self.flood_log = tk.Text(tab_global, wrap=tk.WORD, font=("Helvetica", 9), bg="#efeef3", bd=0, padx=4, pady=4, yscrollcommand=sb1.set)
        self.flood_log.pack(fill=tk.BOTH, expand=True)
        sb1.config(command=self.flood_log.yview)

        sb2 = tk.Scrollbar(tab_conv)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.convergence_log_box = tk.Text(tab_conv, wrap=tk.WORD, font=("Courier New", 9), bg="#1e272e", fg="white", bd=0, padx=4, pady=4, yscrollcommand=sb2.set)
        self.convergence_log_box.pack(fill=tk.BOTH, expand=True)
        sb2.config(command=self.convergence_log_box.yview)

        self.flood_log.tag_config("init",      foreground="#7f8c8d")
        self.flood_log.tag_config("hello_tx",  foreground="#0984e3", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hello_rx",  foreground="#00b894", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("sent",      foreground="#1e3799", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("received",  foreground="#218c74", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("process",   foreground="#d35400")
        self.flood_log.tag_config("dropped",   foreground="#c0392b", font=("Helvetica", 9, "italic"))
        self.flood_log.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("converged", foreground="#1b1464", background="#fff200", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hmac_ok",   foreground="#27ae60", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hmac_fail", foreground="#ffffff", background="#c0392b", font=("Helvetica", 9, "bold"))
        self.convergence_log_box.tag_config("INITIAL",    foreground="#2ecc71", font=("Courier New", 9, "bold"))
        self.convergence_log_box.tag_config("DISRUPTION", foreground="#f1c40f")

    def build_bottom_inspector_panel(self):
        inspect_frame = tk.LabelFrame(self.left_column, text=" 2. Local Router Dynamic State Inspector Panel ", font=("Helvetica", 11, "bold"), fg="#c0392b", padx=10, pady=10)
        inspect_frame.pack(fill=tk.BOTH, expand=True)

        self.packet_header_lbl = tk.Label(inspect_frame, text="LSA Packet Structure Data: Router A", font=("Helvetica", 10, "bold"), fg="#c0392b")
        self.packet_header_lbl.pack(anchor=tk.W, pady=(2, 2))
        self.lsa_view_box = tk.Text(inspect_frame, height=4, font=("Courier New", 9), bg="#fdf2f2", bd=1, relief=tk.SOLID, padx=5, pady=5)
        self.lsa_view_box.pack(fill=tk.X, pady=(0, 5))

        self.local_log_header_lbl = tk.Label(inspect_frame, text="Contextual Local Port Transmissions Log for Router A:", font=("Helvetica", 10, "bold"), fg="#78281f")
        self.local_log_header_lbl.pack(anchor=tk.W, pady=(2, 2))
        local_log_container = tk.Frame(inspect_frame, bd=1, relief=tk.SOLID, height=110)
        local_log_container.pack(fill=tk.X, pady=(0, 5))
        local_log_container.pack_propagate(False)
        scrollbar_l = tk.Scrollbar(local_log_container)
        scrollbar_l.pack(side=tk.RIGHT, fill=tk.Y)
        self.local_router_log_box = tk.Text(local_log_container, wrap=tk.WORD, font=("Helvetica", 9), bg="#ffffff", fg="#2f3640", bd=0, padx=5, pady=5, yscrollcommand=scrollbar_l.set)
        self.local_router_log_box.pack(fill=tk.BOTH, expand=True)
        scrollbar_l.config(command=self.local_router_log_box.yview)

        self.local_router_log_box.tag_config("init",      foreground="#7f8c8d")
        self.local_router_log_box.tag_config("hello_tx",  foreground="#0984e3", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("hello_rx",  foreground="#00b894", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("sent",      foreground="#1e3799", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("received",  foreground="#218c74", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("process",   foreground="#d35400")
        self.local_router_log_box.tag_config("dropped",   foreground="#c0392b", font=("Helvetica", 9, "italic"))
        self.local_router_log_box.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))

        self.table_header_lbl = tk.Label(inspect_frame, text="AOSPF Routing Table (Based on Learned LSAs): Router A", font=("Helvetica", 10, "bold"), fg="#1b5c8f")
        self.table_header_lbl.pack(anchor=tk.W, pady=(2, 2))
        table_container = tk.Frame(inspect_frame, bd=1, relief=tk.SOLID)
        table_container.pack(fill=tk.BOTH, expand=True)
        scrollbar_t = tk.Scrollbar(table_container)
        scrollbar_t.pack(side=tk.RIGHT, fill=tk.Y)
        self.table_view_box = tk.Text(table_container, font=("Courier New", 9), bg="#f8f9fa", bd=0, padx=5, pady=5, yscrollcommand=scrollbar_t.set)
        self.table_view_box.pack(fill=tk.BOTH, expand=True)
        scrollbar_t.config(command=self.table_view_box.yview)

    def build_graph_canvas(self):
        self.fig_f, self.ax_f = plt.subplots(figsize=(9, 7.5))
        self.canvas_f = FigureCanvasTkAgg(self.fig_f, master=self.right_column)
        self.canvas_f.get_tk_widget().grid(row=0, column=0, sticky="nswe")
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
            if d < closest_dist: closest_dist = d; closest_node = node
        if closest_dist <= 0.25 and closest_node:
            self.selected_node = closest_node
            if self.simulation_started: self.render_all_views()
            else: self.render_base_configuration_graph()
            return
        closest_edge, closest_edge_dist = None, float('inf')
        for u, v in self.G.edges():
            x1, y1 = self.node_positions[u]; x2, y2 = self.node_positions[v]
            dx, dy = x2 - x1, y2 - y1
            mag2 = dx*dx + dy*dy
            if mag2 == 0: continue
            t = max(0, min(1, ((x0-x1)*dx + (y0-y1)*dy) / mag2))
            d = ((x0 - x1 - t*dx)**2 + (y0 - y1 - t*dy)**2)**0.5
            if d < closest_edge_dist: closest_edge_dist = d; closest_edge = tuple(sorted((u, v)))
        if closest_edge_dist <= 0.15 and closest_edge:
            self.selected_edge = closest_edge
            if self.simulation_started: self.render_all_views()
            else: self.render_base_configuration_graph()

    # -------------------------------------------------------
    # GRAPH RENDER — CONFIGURATION MODE
    # -------------------------------------------------------
    def render_base_configuration_graph(self):
        self.ax_f.clear()
        nc = ['#1e3799' if n == self.selected_node else '#dcdde1' for n in sorted(self.G.nodes())]
        for u, v in self.G.edges():
            et = tuple(sorted((u, v)))
            c = '#a29bfe' if et == self.selected_edge else '#2c3e50'
            w = 6.0 if et == self.selected_edge else 1.5
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color=c, width=w, ax=self.ax_f)
        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=nc, node_size=400, edgecolors='#2c3e50', ax=self.ax_f)
        for name, (x, y) in self.node_positions.items():
            fc = 'white' if name == self.selected_node else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=10, fontweight='bold', ha='center', va='center', color=fc)
        el = {(u, v): f"C:{d['cost']}|{d['bandwidth'].replace('Mbps','M').replace('Gbps','G').replace('Kbps','K')}|{d['delay']}ms" for u, v, d in self.G.edges(data=True)}
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=el, font_size=8, font_weight='bold', ax=self.ax_f, rotate=True, bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#b2bec3', alpha=0.85))
        topo_name = self.topology_combo.get() if hasattr(self, 'topology_combo') else ''
        self.ax_f.set_title(f"AOSPF Topology — Configuration Mode  |  HMAC-SHA256 Secured  [{topo_name}]", fontsize=10, fontweight='bold', color="#2c3e50")
        self.ax_f.axis('off')
        self.canvas_f.draw()
        self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
        self.delay_change_combo.config(state="disabled")
        self.packet_header_lbl.config(text=f"LSA Packet Structure Data: Router {self.selected_node}")
        self.local_log_header_lbl.config(text=f"Contextual Local Port Transmissions Log for Router {self.selected_node}:")
        self.table_header_lbl.config(text=f"AOSPF Routing Table (Simulation Offline): Router {self.selected_node}")

    # -------------------------------------------------------
    # RUNTIME PANELS
    # -------------------------------------------------------
    def update_text_panels_data(self):
        target = self.selected_node
        T = self.current_time_ms
        state = self.timeline_states[T]

        if self.selected_edge is None:
            self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
            self.delay_change_combo.config(state="disabled")
        else:
            u, v = self.selected_edge
            self.delay_change_combo.config(state="readonly")
            self.delay_change_combo.set(str(state["get_delay_func"](u, v, T)))
            if self.selected_edge in state['broken_links']:
                self.link_toggle_btn.config(text=f"Enable Link {u}-{v} 🟢", state="normal", bg="#27ae60", fg="#ffffff")
            else:
                self.link_toggle_btn.config(text=f"Disable Link {u}-{v} 🔴", state="normal", bg="#c0392b", fg="#ffffff")

        if state["is_true_converged"]:
            self.convergence_indicator_lbl.config(text=f"🟢 Topology Converged & Stable [Time: {format_time(state['true_convergence_time'])}]", bg="#d4edda", fg="#155724")
        elif state["is_protocol_converged"]:
            if state.get("is_delay_cost_discrepancy", False):
                self.convergence_indicator_lbl.config(text="🟡 Stable but Inaccurate (Delay Cost Discrepancy)", bg="#fff3cd", fg="#856404")
            else:
                self.convergence_indicator_lbl.config(text="🟡 Stable but Inaccurate", bg="#fff3cd", fg="#856404")
        else:
            self.convergence_indicator_lbl.config(text="⚠️ Syncing Map Data...", bg="#ffeaa7", fg="#d35400")

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

        self.packet_header_lbl.config(text=f"LSA Packet Structure Data: Router {target}")
        self.local_log_header_lbl.config(text=f"Contextual Local Port Transmissions Log for Router {target}:")
        self.table_header_lbl.config(text=f"AOSPF Routing Table ({format_time(T)} Database Snapshot): Router {target}")

        self.lsa_view_box.delete('1.0', tk.END)
        if target in known:
            lsa = known[target]
            self.lsa_view_box.insert(tk.END, f"• Source ID: Router_{target} | Seq: {lsa['sequence_num']} | TTL: {lsa['ttl']}\n")
            self.lsa_view_box.insert(tk.END, "• Advertised Metric Boundaries (Operational Neighbors Only):\n")
            costs = [f"Link {target}->{k} (Cost: {v})" for k, v in lsa['neighbors'].items()]
            self.lsa_view_box.insert(tk.END, "  " + (", ".join(costs) if costs else "None (Interfaces Down)"))
        else:
            self.lsa_view_box.insert(tk.END, f"• Source ID: Router_{target} | Seq: -- | Status: DOWN\nNo LSA data generated or stored inside local workspace.")

        self.local_router_log_box.config(state=tk.NORMAL)
        self.local_router_log_box.delete('1.0', tk.END)
        found = False
        for log_t, text, tag in self.router_events[target]:
            if log_t <= T:
                found = True
                self.local_router_log_box.insert(tk.END, f"[{format_time(log_t)}] {text}\n", tag)
        if not found:
            self.local_router_log_box.insert(tk.END, "No events recorded yet.")
        self.local_router_log_box.config(state=tk.DISABLED)
        self.local_router_log_box.see(tk.END)

        self.table_view_box.delete('1.0', tk.END)
        header = f"{'Destination':<12} | {'Metric Cost':<11} | {'Next Hop':<9} | {'Computed Path Vector':<20}\n"
        self.table_view_box.insert(tk.END, header)
        self.table_view_box.insert(tk.END, f"{'-'*64}\n")
        for dest in sorted(n for n in local_G.nodes() if n != target):
            if dest in paths:
                cost_metric = str(lengths[dest])
                pv = paths[dest]
                nh = pv[1] if len(pv) > 1 else dest
                self.table_view_box.insert(tk.END, f"Network {dest:<4} | {cost_metric:<11} | Router {nh:<2} | {' -> '.join(pv)}\n")

    def next_timeline_step(self):
        step = int(self.step_combo.get())
        target = self.current_time_ms + step
        while len(self.timeline_states) <= target:
            next(self.sim_generator)
        self.current_time_ms = target
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
    # GRAPH RENDER — SIMULATION MODE
    # -------------------------------------------------------
    def render_flooding_state_view(self):
        self.ax_f.clear()
        T = self.current_time_ms
        state = self.timeline_states[T]

        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        for e in self.logs_database:
            if e["time"] <= T:
                self.flood_log.insert(tk.END, f"[{format_time(e['time'])}] {e['text']}\n", e["type"])
        self.flood_log.config(state=tk.DISABLED)
        self.flood_log.see(tk.END)

        self.convergence_log_box.config(state=tk.NORMAL)
        self.convergence_log_box.delete('1.0', tk.END)
        found_metrics = False
        for item in self.convergence_metrics_database:
            if item["time"] <= T:
                found_metrics = True
                self.convergence_log_box.insert(tk.END, f"[{format_time(item['time'])}] {item['text']}\n", item["type"])
        if not found_metrics:
            self.convergence_log_box.insert(tk.END, "No convergence events yet.")
        self.convergence_log_box.config(state=tk.DISABLED)
        self.convergence_log_box.see(tk.END)

        self.flood_matrix_text.delete('1.0', tk.END)
        self.flood_matrix_text.insert(tk.END, f"{'Node':<6} | LSDB contents\n{'-'*40}\n")
        for node, d in sorted(state['lsdb'].items()):
            self.flood_matrix_text.insert(tk.END, f"  {node:<4} | {{{', '.join(sorted(d.keys()))}}}\n")

        total = len(self.G.nodes())
        nc = []
        for n in sorted(self.G.nodes()):
            if n == self.selected_node:             nc.append('#1e3799')
            elif len(state['lsdb'][n]) == total:    nc.append('#2ecc71')
            elif len(state['lsdb'][n]) > 0:         nc.append('#e84118')
            else:                                    nc.append('#dcdde1')

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
                nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color='#a29bfe', width=8.0, alpha=0.6, ax=self.ax_f)
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color=col, width=wid, style=sty, ax=self.ax_f)

        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=nc, node_size=400, edgecolors='#2c3e50', ax=self.ax_f)
        for name, (x, y) in self.node_positions.items():
            fc = 'white' if name == self.selected_node or len(state['lsdb'][name]) > 0 else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=10, fontweight='bold', ha='center', va='center', color=fc)

        el = {}
        for u, v, d in self.G.edges(data=True):
            et = tuple(sorted((u, v)))
            if et in state['broken_links']:
                status = "TO" if (state['adj_states'][u][v]=="DOWN" or state['adj_states'][v][u]=="DOWN") else "HD"
            else:
                status = f"C:{state['advertised_costs'][u][v]}"
            delay = state['get_delay_func'](u, v, T)
            bw = self.original_edges_data.get(et, {}).get('bandwidth', '')
            bw_short = bw.replace('Mbps','M').replace('Gbps','G').replace('Kbps','K')
            el[(u, v)] = f"{status}|{bw_short}|{delay}ms"
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=el, font_size=8, font_weight='bold', ax=self.ax_f, rotate=True, bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#b2bec3', alpha=0.85))

        topo_name = self.topology_combo.get() if hasattr(self, 'topology_combo') else ''
        if self.attack_injected and self.attack_inject_time is not None and T >= self.attack_inject_time:
            self.ax_f.set_title(f"AOSPF Clock: {format_time(T)}  |  ATTACK BLOCKED by HMAC  [{topo_name}]", fontsize=10, fontweight='bold', color="#27ae60")
        else:
            self.ax_f.set_title(f"AOSPF Clock: {format_time(T)}  |  HMAC-SHA256 Secured  [{topo_name}]", fontsize=10, fontweight='bold', color="#2c3e50")
        self.ax_f.axis('off')
        self.canvas_f.draw()


if __name__ == '__main__':
    window_root = tk.Tk()
    application = AOSPFAsynchronousWorkspaceDashboard(window_root)
    window_root.mainloop()