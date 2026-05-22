import tkinter as tk
from tkinter import ttk
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import json
import os
import math

class aospfAsynchronousWorkspaceDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("aospf Unified Engine: Asynchronous Multi-Convergence Simulation")
        self.root.geometry("1550x950")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # aospf Protocol Timer Configurations (in milliseconds)
        self.hello_interval = 3000
        self.dead_interval = 10000

        # Composite Cost Formula Parameters
        self.w1 = 10.0
        self.w2 = 1.0
        self.L_max = 50.0  # Normalized maximum delay bound matching UI dropdown options

        # Persistent Global Convergence Database Metrics Buffer
        self.convergence_metrics_database = []

        # 1. Load topology from topology_5.json
        self.G = nx.Graph()
        self._load_topology()
        
    def _load_topology(self):
        """Load network topology from topology_5.json file."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        topology_path = os.path.join(script_dir, 'topology_5.json')
        
        if not os.path.exists(topology_path):
            raise FileNotFoundError(
                f"topology_5.json not found at: {topology_path}\n"
                "Please create a topology_5.json file with 'nodes' and 'edges' keys."
            )
        
        with open(topology_path, 'r') as f:
            data = json.load(f)
        
        # Build node positions from file with a 2.5x spacing scalar to make lines longer
        self.node_positions = {}
        for node in data.get('nodes', []):
            self.node_positions[node['id']] = (node['x'] * 2.5, node['y'] * 2.5)
        
        # Build edge list and graph from file
        self.edges_definition = []
        self.original_edges_data = {}
        self.G.clear()
        
        # Standard aospf reference bandwidth = 1000 Mbps (1 Gbps, modern default)
        REFERENCE_BW_MBPS = 1000
        
        def parse_bandwidth_mbps(bw_str):
            """Parse a bandwidth string like '500Mbps' or '1Gbps' into Mbps float."""
            import re
            m = re.match(r'(\d+(?:\.\d+)?)(Gbps|Mbps|Kbps)', bw_str, re.IGNORECASE)
            if not m:
                return 100.0  # default 100 Mbps
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
            # aospf cost = ceil(reference_bandwidth / link_bandwidth), minimum 1
            cost = max(1, math.ceil(REFERENCE_BW_MBPS / bw_mbps))
            self.edges_definition.append((u, v, cost, delay))
            self.G.add_edge(u, v, cost=cost, bandwidth=bw_str, delay=delay)
            self.original_edges_data[tuple(sorted((u, v)))] = {
                'cost': cost, 'bandwidth': bw_str, 'bandwidth_mbps': bw_mbps, 'delay': delay
            }
        
        # Set selected_node to the first node in the topology
        all_nodes = sorted(self.node_positions.keys())
        self.selected_node = all_nodes[0] if all_nodes else 'A'

        # Constant internal node computational processing delay
        self.node_processing_delay = 3 # 3ms internal packet validation overhead

        # Lifecycle State Trackers
        self.simulation_started = False
        self.current_time_ms = 0
        self.simulation_running = False
        self.after_id = None
        self.selected_edge = None # Tracks currently selected link path interface
        self.link_toggles = [] # Dynamic structural disruption change logging database
        self.delay_changes = [] # Dynamic property runtime delay adjustment logs
        self.cost_changes  = [] # Retained internally for fallback validation paths

        # Build UI Panels
        self.setup_ui()
        
        # Initial Configuration Baseline Render
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
        """Extracts configuration parameters and triggers the discrete event simulator."""
        self.hello_interval = int(self.hello_combo.get())
        self.dead_interval = self.hello_interval * 4 
        self.w1 = float(self.w1_combo.get())
        self.w2 = float(self.w2_combo.get())
        self.current_time_ms = 0
        self.link_toggles = [] 
        self.delay_changes = []
        self.cost_changes  = []
        self.selected_edge = None
        self.convergence_metrics_database = []  # Clear only when a fresh run is initialized
        
        # Execute Engine Compilation Pass
        self.sim_generator = self.run_continuous_event_simulation()
        next(self.sim_generator)
        self.simulation_started = True
        self.simulation_running = True
        
        # Update Control Widget Lock States
        self.hello_combo.config(state="disabled")
        self.w1_combo.config(state="disabled")
        self.w2_combo.config(state="disabled")
        self.start_btn.config(text="⏸ Pause", command=self.toggle_pause)
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
        """Wipes the timeline history records and forces return to configuration mode."""
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.simulation_started = False
        self.simulation_running = False
        self.current_time_ms = 0
        self.selected_edge = None
        self.link_toggles = []
        self.delay_changes = []
        self.cost_changes  = []
        self.convergence_metrics_database = []  # Completely reset buffer history
        
        # Unlock Configuration Elements / Lock Playback Actions
        self.hello_combo.config(state="readonly")
        self.w1_combo.config(state="readonly")
        self.w2_combo.config(state="readonly")
        self.start_btn.config(text="Start Simulation 🚀", command=self.start_simulation, state="normal")
        self.prev_btn.config(state="disabled")
        self.next_btn.config(state="disabled")
        self.sync_btn.config(state="disabled")
        self.reset_btn.config(state="normal")
        
        # Reset text tracking fields
        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        self.flood_log.insert(tk.END, "⚙️ SYSTEM ADJACENCY IDLE MODE\nConfigure metrics above, then click 'Start Simulation 🚀' to execute the protocol state machine sequence.")
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
        
        self.convergence_indicator_lbl.config(text="🛑 Simulation Not Started", bg="#dcdde1", fg="#2c3e50")
        
        self.render_base_configuration_graph()

    def toggle_selected_link(self):
        """Commits an administrative link fail/restore event to the simulation timeline."""
        if self.selected_edge and self.simulation_started:
            self.link_toggles.append((self.selected_edge, self.current_time_ms))
            self._rebuild_history()
            self.render_all_views()

    def apply_runtime_delay_change(self, event=None):
        """Injects a runtime link delay adjustment sequence record into the event timeline matrix."""
        if self.selected_edge and self.simulation_started:
            new_delay = int(self.delay_change_combo.get())
            self.delay_changes.append((self.selected_edge, new_delay, self.current_time_ms))
            
            u, v = self.selected_edge
            self.logs_database.append({
                "time": self.current_time_ms,
                "text": f"🔧 PROPAGATION MODIFICATION: Latency delay on interface link {u}-{v} modified to {new_delay}ms at runtime.",
                "routers": [u, v],
                "type": "process"
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
    # TIME-VARYING PARAMETER DISCRETE SIMULATION ENGINE
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
        pending_cost_tracks = [] # Tracks threshold metric cost shifts

        # Track currently actively utilized/advertised database routing metrics locally per node interface
        advertised_costs = {n: {nbr: self.original_edges_data[tuple(sorted((n, nbr)))]['cost'] for nbr in self.G.neighbors(n)} for n in nodes}

        # Helper to compute time-dependent link propagation delays
        def get_current_delay(u_node, v_node, eval_time):
            e_tuple = tuple(sorted((u_node, v_node)))
            base_delay = self.original_edges_data[e_tuple]['delay']
            for mod_edge, mod_delay, timestamp in self.delay_changes:
                if mod_edge == e_tuple and timestamp <= eval_time:
                    base_delay = mod_delay
            return base_delay

        # Helper to compute time-dependent link aospf base costs
        def get_current_cost(u_node, v_node, eval_time):
            e_tuple = tuple(sorted((u_node, v_node)))
            base_cost = self.original_edges_data[e_tuple]['cost']
            return base_cost

        # --- SEED INITIAL HELLO TRANSMISSION EVENTS ---
        self.logs_database.append({
            "time": 0, "text": f"System Boot Initialization: All routers schedule periodic HELLO transmissions every {self.hello_interval}ms.", "routers": list(nodes), "type": "init"
        })
        for n in nodes:
            event_queue.append((0, "HELLO_SEND", (n,)))

        self.timeline_states = {}
        last_logged_state = "RED" 
        initial_sync_logged = len([x for x in self.convergence_metrics_database if x["type"] == "INITIAL"]) > 0
        last_protocol_instability = 0
        last_true_instability = 0
        
        current_time = 0
        while True:
            active_protocol_disruption = False

            # Evaluate interactive runtime link toggles
            for edge, toggle_time in self.link_toggles:
                if toggle_time == current_time:
                    u, v = edge
                    if edge in broken_links:
                        broken_links.remove(edge)
                        self.logs_database.append({
                            "time": current_time, "text": f"🛠️ LINK RESTORED: Physical connection established between Router {u} and Router {v}. Awaiting periodic HELLO discovery.", "routers": [u, v], "type": "process"
                        })
                        self.router_events[u].append((current_time, f"Physical link layer to Router {v} restored. Interface status UP, waiting for background periodic HELLO timer.", "init"))
                        self.router_events[v].append((current_time, f"Physical link layer to Router {u} restored. Interface status UP, waiting for background periodic HELLO timer.", "init"))
                    else:
                        broken_links.add(edge)
                        pending_failure_tracks.append({
                            "edge": edge, "t_fail": current_time, "t_timeout": None
                        })
                        self.logs_database.append({
                            "time": current_time, "text": f"💥 LINK SEVERED: Cable cut between Router {u} and Router {v}. Dropping packets; awaiting interface Hello keepalive timeouts.", "routers": [u, v], "type": "dropped"
                        })
                        self.router_events[u].append((current_time, f"Link interface route to Router {v} broken. Packet dropping active, waiting for Hello dead timer to trip.", "dropped"))
                        self.router_events[v].append((current_time, f"Link interface route to Router {u} broken. Packet dropping active, waiting for Hello dead timer to trip.", "dropped"))

            # --- aospf PROTOCOL DEAD TIMER MONITORING MATRICES ---
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
                                "routers": [u, nbr],
                                "type": "dropped"
                            })
                            self.router_events[u].append((current_time, f"Dead Timer Timeout for Router {nbr} ({self.dead_interval}ms passed). Tearing down adjacency interface.", "dropped"))
                            
                            # Fire updated corrective LSA metrics advertisements
                            lsa_seq[u] += 1
                            active_nbrs = {k: advertised_costs[u][k] for k in self.G.neighbors(u) if adj_states[u][k] == "2WAY"}
                            lsa_payload = {
                                "router_id": u, "sequence_num": lsa_seq[u], "ttl": 64, "neighbors": active_nbrs
                            }
                            current_lsdb[u][u] = lsa_payload
                            self.router_events[u].append((current_time, f"Generated updated topology Router-LSA (Seq: {lsa_seq[u]}) isolating dead interface.", "db_update"))
                            
                            for flooded_nbr in self.G.neighbors(u):
                                if adj_states[u][flooded_nbr] == "2WAY":
                                    link_prop_delay = get_current_delay(u, flooded_nbr, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (u, flooded_nbr, lsa_payload, link_prop_delay)))
                                    self.router_events[u].append((current_time, f"Flooded corrective update LSA forward to neighbor Router {flooded_nbr}.", "sent"))

            event_queue.sort(key=lambda x: x[0])
            
            # Process current millisecond events
            while event_queue and event_queue[0][0] == current_time:
                t_curr, ev_type, data = event_queue.pop(0)
                
                if ev_type == "HELLO_SEND":
                    router = data[0]
                    active_neighbors = [k for k, v in adj_states[router].items() if v in ["INIT", "2WAY"]]
                    
                    if current_time > 0:
                        self.logs_database.append({
                            "time": current_time,
                            "text": f"Periodic keepalive aospf HELLO broadcast sent from Router {router} out of interfaces.",
                            "routers": [router],
                            "type": "hello_tx"
                        })
                        self.router_events[router].append((current_time, "Sent periodic aospf HELLO keepalive broadcast window frame out of interfaces.", "hello_tx"))
                    
                    for nbr in self.G.neighbors(router):
                        delay = get_current_delay(router, nbr, current_time)
                        event_queue.append((current_time + delay, "HELLO_ARRIVE", (router, nbr, list(active_neighbors), delay, current_time)))
                    event_queue.append((current_time + self.hello_interval, "HELLO_SEND", (router,)))

                elif ev_type == "HELLO_ARRIVE":
                    sender, receiver, sender_neighbor_list, link_delay, sent_time = data
                    if tuple(sorted((sender, receiver))) in broken_links:
                        continue 
                        
                    last_hello_time[receiver][sender] = current_time
                    
                    # --- DYNAMIC COMPOSITE COST MATHEMATICAL EXTRACTION ENGINE ---
                    measured_delay = current_time - sent_time
                    base_cost = get_current_cost(receiver, sender, current_time)
                    
                    # Execute composite formula algebra pass
                    temp_cost = math.ceil(self.w1 * (measured_delay / self.L_max) + self.w2 * base_cost)
                    old_advertised_cost = advertised_costs[receiver][sender]
                    
                    # Detailed cost breakdown audit parameters logged natively inside the transmission log profile
                    comparison_msg = (
                        f"Cost Evaluation for link to {sender}: Measured Delay = {measured_delay}ms -> Temp Cost = {temp_cost} "
                        f"(w1*L/Lmax + w2*C_base = {self.w1}*({measured_delay}/{self.L_max}) + {self.w2}*{base_cost}). "
                        f"Previous Advertised Cost = {old_advertised_cost}."
                    )
                    self.router_events[receiver].append((current_time, comparison_msg, "hello_rx"))
                    
                    if receiver in sender_neighbor_list:
                        if adj_states[receiver][sender] != "2WAY":
                            adj_states[receiver][sender] = "2WAY"
                            active_protocol_disruption = True 
                            advertised_costs[receiver][sender] = temp_cost  # Initialize baseline metrics
                            
                            self.router_events[receiver].append((current_time, f"Received reflective Hello from Router {sender}. Handshake complete: 2-WAY achieved.", "hello_rx"))
                            
                            lsa_triggered[receiver] = True
                            lsa_seq[receiver] += 1
                            active_nbrs = {k: advertised_costs[receiver][k] for k in self.G.neighbors(receiver) if adj_states[receiver][k] == "2WAY"}
                            lsa_payload = {
                                "router_id": receiver, "sequence_num": lsa_seq[receiver], "ttl": 64, "neighbors": active_nbrs
                            }
                            current_lsdb[receiver][receiver] = lsa_payload
                            self.router_events[receiver].append((current_time, f"Triggered optimization LSA metrics re-generation pass (Seq: {lsa_seq[receiver]}).", "db_update"))
                            
                            for nbr in self.G.neighbors(receiver):
                                if adj_states[receiver][nbr] == "2WAY":
                                    link_prop_delay = get_current_delay(receiver, nbr, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (receiver, nbr, lsa_payload, link_prop_delay)))
                                    self.router_events[receiver].append((current_time, f"Flooded updated database LSA map forward onto route to Router {nbr}.", "sent"))
                            
                            # --- DATABASE EXCHANGE: Send all known LSAs to the new neighbor ---
                            for lsa_owner, lsa_entry in current_lsdb[receiver].items():
                                if lsa_owner != receiver:  # Own LSA already sent above
                                    link_prop_delay = get_current_delay(receiver, sender, current_time)
                                    event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (receiver, sender, lsa_entry, link_prop_delay)))
                                    self.router_events[receiver].append((current_time, f"DB Exchange: Sent cached LSA [Router_{lsa_owner}] to new neighbor Router {sender}.", "sent"))
                        else:
                            self.logs_database.append({
                                "time": current_time,
                                "text": f"Routine keepalive HELLO received at Router {receiver} from neighbor Router {sender} (Dead timer refreshed).",
                                "routers": [sender, receiver],
                                "type": "hello_rx"
                            })
                            
                            # CRITICAL PROFILE EXPIRED THRESHOLD EVALUATION PASSTHRU (BI-DIRECTIONAL 40% Check)
                            if temp_cost >= 1.4 * old_advertised_cost or temp_cost <= 0.6 * old_advertised_cost:
                                active_protocol_disruption = True
                                advertised_costs[receiver][sender] = temp_cost
                                
                                edge_key = tuple(sorted((sender, receiver)))
                                t_change = 0
                                for mod_edge, _, timestamp in self.delay_changes:
                                    if mod_edge == edge_key and timestamp <= current_time:
                                        t_change = max(t_change, timestamp)
                                
                                pending_cost_tracks.append({
                                    "edge": edge_key,
                                    "t_change": t_change,
                                    "t_detection": current_time
                                })
                                
                                change_direction = "increased" if temp_cost >= 1.4 * old_advertised_cost else "decreased"
                                self.logs_database.append({
                                    "time": current_time,
                                    "text": f"📈 COST METRIC CHANGE: Dynamic metric cost to neighbor Router {sender} {change_direction} by >= 40% (New Cost: {temp_cost}, Old: {old_advertised_cost}). Dispatching triggered update LSA.",
                                    "routers": [receiver, sender],
                                    "type": "process"
                                })
                                self.router_events[receiver].append((current_time, f"Dynamic cost to Router {sender} hit trigger threshold (+/-40%). Issuing active link update LSA (Seq: {lsa_seq[receiver]+1}).", "db_update"))
                                
                                lsa_seq[receiver] += 1
                                active_nbrs = {k: advertised_costs[receiver][k] for k in self.G.neighbors(receiver) if adj_states[receiver][k] == "2WAY"}
                                lsa_payload = {
                                    "router_id": receiver, "sequence_num": lsa_seq[receiver], "ttl": 64, "neighbors": active_nbrs
                                }
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
                        continue 
                    
                    active_protocol_disruption = True 
                    owner = incoming_payload["router_id"]
                    self.logs_database.append({
                        "time": current_time, "text": f"Packet carrying {owner}'s LSA arrives at Router {receiver} from Router {sender}.", "routers": [sender, receiver], "type": "received"
                    })
                    self.router_events[receiver].append((current_time, f"Received LSA packet [Origin: Router {owner}, Seq: {incoming_payload['sequence_num']}] from neighbor Router {sender}.", "received"))
                    
                    cached_seq = current_lsdb[receiver].get(owner, {}).get("sequence_num", 0)
                    if incoming_payload["sequence_num"] > cached_seq:
                        t_process_finish = current_time + self.node_processing_delay
                        event_queue.append((t_process_finish, "LSA_PROCESS", (receiver, incoming_payload, sender)))
                        self.router_events[receiver].append((current_time, f"LSA is newer than cached sequence ({cached_seq}). Scheduling local port LSA flood processing in +{self.node_processing_delay}ms.", "process"))
                    else:
                        self.router_events[receiver].append((current_time, f"Dropped duplicate LSA [Origin: Router {owner}] (Suppression active).", "dropped"))
                        
                elif ev_type == "LSA_PROCESS":
                    router, incoming_payload, arrival_port = data
                    active_protocol_disruption = True 
                    owner = incoming_payload["router_id"]
                    cached_seq = current_lsdb[router].get(owner, {}).get("sequence_num", 0)
                    
                    if incoming_payload["sequence_num"] > cached_seq:
                        current_lsdb[router][owner] = incoming_payload
                        self.logs_database.append({
                            "time": current_time, "text": f"Router {router} updates local LSDB database maps for [Router_{owner}].", "routers": [router], "type": "db_update"
                        })
                        self.router_events[router].append((current_time, f"Stored updated [Router_{owner}] advertisement map into local LSDB database.", "db_update"))
                        
                        for nbr in self.G.neighbors(router):
                            if nbr != arrival_port and adj_states[router][nbr] == "2WAY":
                                link_prop_delay = get_current_delay(router, nbr, current_time)
                                event_queue.append((current_time + link_prop_delay, "LSA_ARRIVE", (router, nbr, incoming_payload, link_prop_delay)))
                                self.router_events[router].append((current_time, f"Sent LSA forward [Origin: Router {owner}] flooded out to neighbor Router {nbr}.", "sent"))

            # --- DUAL-DIRECTION OMNISCIENT OBSERVER VALIDATION ENGINE ---
            operational_nodes = [n for n in nodes if any(status == "2WAY" for status in adj_states[n].values())]
            
            is_synchronized = False
            if operational_nodes:
                ref_db = current_lsdb[operational_nodes[0]]
                is_synchronized = True
                for n in operational_nodes:
                    if current_lsdb[n].keys() != ref_db.keys():
                        is_synchronized = False
                        break
                    for k in ref_db:
                        if current_lsdb[n][k]["sequence_num"] != ref_db[k]["sequence_num"]:
                                is_synchronized = False
                                break
                                
            is_physically_accurate = True
            for u, v in self.G.edges():
                edge_tuple = tuple(sorted((u, v)))
                is_broken = edge_tuple in broken_links
                for n in nodes:
                    u_has_v = v in current_lsdb[n].get(u, {}).get("neighbors", {})
                    v_has_u = u in current_lsdb[n].get(v, {}).get("neighbors", {})
                    if is_broken:
                        if u_has_v or v_has_u:
                            is_physically_accurate = False
                            break
                    else:
                        if not (u_has_v and v_has_u):
                            is_physically_accurate = False
                            break
                if not is_physically_accurate:
                    break

            # Independent outside-sense dynamic delay cost discrepancy evaluation engine
            is_delay_cost_discrepancy = False
            for u_node, v_node in self.G.edges():
                edge_tuple = tuple(sorted((u_node, v_node)))
                if edge_tuple in broken_links:
                    continue
                l_delay = get_current_delay(u_node, v_node, current_time)
                b_cost = get_current_cost(u_node, v_node, current_time)
                true_cost = math.ceil(self.w1 * (l_delay / self.L_max) + self.w2 * b_cost)
                
                old_u = advertised_costs[u_node][v_node]
                old_v = advertised_costs[v_node][u_node]
                
                if true_cost != old_u or true_cost != old_v:
                    if (true_cost >= 1.4 * old_u or true_cost <= 0.6 * old_u) or (true_cost >= 1.4 * old_v or true_cost <= 0.6 * old_v):
                        is_delay_cost_discrepancy = True
                        break

            has_pending_lsas = any(ev[1] in ["LSA_ARRIVE", "LSA_PROCESS"] for ev in event_queue)

            if active_protocol_disruption or has_pending_lsas or not is_synchronized:
                last_protocol_instability = current_time
            is_protocol_converged = (current_time > last_protocol_instability) and (len(operational_nodes) > 0)

            # Instability maps cost shifts as discrepancies in absolute reality pass bounds
            if active_protocol_disruption or has_pending_lsas or not is_synchronized or not is_physically_accurate or is_delay_cost_discrepancy:
                last_true_instability = current_time
            is_true_converged = (current_time > last_true_instability) and (len(operational_nodes) > 0)

            # --- DISCRETE CONVERGENCE TRANSACTION METRICS LOGGER ---
            current_state_str = "RED"
            if is_true_converged:
                current_state_str = "GREEN"
            elif is_protocol_converged:
                if is_delay_cost_discrepancy:
                    current_state_str = "YELLOW_DELAY"
                else:
                    current_state_str = "YELLOW"

            if current_state_str != last_logged_state:
                if current_state_str == "GREEN":
                    self.logs_database.append({
                        "time": current_time, 
                        "text": f"⭐ aospf NETWORK TOPOLOGY CONVERGENCE ACHIEVED! All local database maps are synchronized completely identical and accurate to physical wire states.", 
                        "routers": list(nodes), 
                        "type": "converged"
                    })
                    
                    if not initial_sync_logged:
                        initial_sync_logged = True
                        self.convergence_metrics_database.append({
                            "time": current_time,
                            "type": "INITIAL",
                            "text": f"📌 [Initial Network Initialization Pass]\n• Time to Reach Initial Synchronization: {current_time} ms from system boot frame.\n"
                        })
                    
                    for item in list(pending_failure_tracks):
                        if item["t_timeout"] is not None:
                            t_fail = item["t_fail"]
                            t_timeout = item["t_timeout"]
                            
                            duration_from_fail = current_time - t_fail
                            duration_from_timeout = current_time - t_timeout
                            u, v = item["edge"]
                            
                            msg = (
                                f"⚡ [Link Failure Recovery Profile: Interrupted Interface Path {u} - {v}]\n"
                                f"  • Total Time to Synchronize After Physical Link Failure: {duration_from_fail} ms (Disrupted at t={t_fail} ms)\n"
                                f"  • Time to Synchronize After Fault Detection (Dead Timer Expiry): {duration_from_timeout} ms (Alerted at t={t_timeout} ms)\n"
                            )
                            # Duplication gate check before writing
                            if not any(x["text"] == msg and x["time"] == current_time for x in self.convergence_metrics_database):
                                self.convergence_metrics_database.append({
                                    "time": current_time, "type": "DISRUPTION", "text": msg
                                })
                            pending_failure_tracks.remove(item)

                    for item in list(pending_cost_tracks):
                        t_change = item["t_change"]
                        t_detection = item["t_detection"]
                        duration_from_change = current_time - t_change
                        duration_from_detection = current_time - t_detection
                        u, v = item["edge"]
                        
                        msg = (
                            f"📈 [Cost Metric Dynamic Shift Profile: Link {u} - {v}]\n"
                            f"  • Total Time to Synchronize After Physical Delay Alteration (Outside Sense): {duration_from_change} ms (Altered at t={t_change} ms)\n"
                            f"  • Time to Synchronize After Threshold Detection by Router: {duration_from_detection} ms (Detected at t={t_detection} ms)\n"
                        )
                        # Duplication gate check before writing
                        if not any(x["text"] == msg and x["time"] == current_time for x in self.convergence_metrics_database):
                            self.convergence_metrics_database.append({
                                "time": current_time, "type": "DISRUPTION", "text": msg
                            })
                        pending_cost_tracks.remove(item)

                elif current_state_str == "YELLOW_DELAY":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "aospf link delay cost discrepancy detected in outside sense (Awaiting Hello detection handshake).",
                        "routers": list(nodes),
                        "type": "process"
                    })
                elif current_state_str == "YELLOW":
                    self.logs_database.append({
                        "time": current_time,
                        "text": "aospf network state synchronized, but inaccurate to physical map (Topology discrepancy window active).",
                        "routers": list(nodes),
                        "type": "process"
                    })
                
                last_logged_state = current_state_str

            # Capture active link transit configurations
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
                "get_cost_func":  get_current_cost,
                "advertised_costs": {n: dict(advertised_costs[n]) for n in nodes},
                "is_delay_cost_discrepancy": is_delay_cost_discrepancy
            }
            yield current_time

            current_time += 1

    # -------------------------------------------------------
    # UI Layout Construction
    # -------------------------------------------------------
    def setup_ui(self):
        self.left_column = tk.Frame(self.root, width=580, padx=10, pady=10)
        self.left_column.pack(side=tk.LEFT, fill=tk.Y)
        self.left_column.pack_propagate(False)

        self.right_column = tk.Frame(self.root, padx=10, pady=10)
        self.right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.build_top_flooding_panel()
        self.build_bottom_inspector_panel()
        self.build_graph_canvas()

    def build_top_flooding_panel(self):
        flood_frame = tk.LabelFrame(self.left_column, text=" 1. Distributed LSA Flooding Synchronization Panel ", font=("Helvetica", 11, "bold"), fg="#2c3e50", padx=10, pady=10)
        flood_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Lifecycle Configuration Segment Box
        config_box = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=5, pady=5)
        config_box.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(config_box, text="Hello (ms):", font=("Helvetica", 9, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=2)
        self.hello_combo = ttk.Combobox(config_box, values=["1000", "2000", "3000", "5000"], state="readonly", width=5)
        self.hello_combo.pack(side=tk.LEFT, padx=2)
        self.hello_combo.set("3000")

        tk.Label(config_box, text="w1:", font=("Helvetica", 9, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=2)
        self.w1_combo = ttk.Combobox(config_box, values=["0", "1", "2", "5", "10", "20", "50"], state="readonly", width=4)
        self.w1_combo.pack(side=tk.LEFT, padx=2)
        self.w1_combo.set("10")

        tk.Label(config_box, text="w2:", font=("Helvetica", 9, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=2)
        self.w2_combo = ttk.Combobox(config_box, values=["0", "1", "2", "5", "10", "20", "50"], state="readonly", width=4)
        self.w2_combo.pack(side=tk.LEFT, padx=2)
        self.w2_combo.set("1")
        
        self.start_btn = tk.Button(config_box, text="Start Simulation 🚀", font=("Helvetica", 9, "bold"), command=self.start_simulation, bg="#27ae60", fg="#ffffff", activebackground="#219653")
        self.start_btn.pack(side=tk.RIGHT, padx=4)

        # LINK DISRUPTION ADMINISTRATOR PANEL
        link_admin_box = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=5, pady=5)
        link_admin_box.pack(fill=tk.X, pady=(0, 5))
        tk.Label(link_admin_box, text="Link Disruption Administrator:", font=("Helvetica", 9, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=2)
        
        self.link_toggle_btn = tk.Button(link_admin_box, text="Select a Link on Map", font=("Helvetica", 10, "bold"), state="disabled", command=self.toggle_selected_link)
        self.link_toggle_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=4)

        # RUNTIME DELAY ADJUSTER SELECTOR
        delay_admin_box = tk.Frame(flood_frame, bd=1, relief=tk.GROOVE, padx=5, pady=5)
        delay_admin_box.pack(fill=tk.X, pady=(0, 5))
        tk.Label(delay_admin_box, text="Runtime Delay Selector (ms):", font=("Helvetica", 9, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=2)
        
        self.delay_change_combo = ttk.Combobox(delay_admin_box, values=["2", "5", "8", "12", "15", "20", "25", "30", "40", "50"], state="disabled", width=8)
        self.delay_change_combo.pack(side=tk.RIGHT, padx=4)
        self.delay_change_combo.bind("<<ComboboxSelected>>", self.apply_runtime_delay_change)

        # Playback navigation size selectors
        step_ctrl_box = tk.Frame(flood_frame)
        step_ctrl_box.pack(fill=tk.X, pady=2)
        
        tk.Label(step_ctrl_box, text="Adjustable Skip Step Size (ms):", font=("Helvetica", 10, "bold"), fg="#2f3640").pack(side=tk.LEFT, padx=2)
        self.step_combo = ttk.Combobox(step_ctrl_box, values=["5", "10", "50", "100", "1000"], state="readonly", width=10)
        self.step_combo.pack(side=tk.LEFT, padx=5)
        self.step_combo.set("100") 

        # Playback stepping controls
        btn_box = tk.Frame(flood_frame)
        btn_box.pack(fill=tk.X, pady=5)
        self.prev_btn = tk.Button(btn_box, text="◀ Prev Step", font=("Helvetica", 11, "bold"), command=self.prev_timeline_step, bg="#222f3e", fg="#ffffff", activebackground="#1e272e", relief=tk.RAISED, bd=3)
        self.prev_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self.next_btn = tk.Button(btn_box, text="Next Step ▶", font=("Helvetica", 11, "bold"), command=self.next_timeline_step, bg="#1e3799", fg="#ffffff", activebackground="#0a3d62", relief=tk.RAISED, bd=3)
        self.next_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=4)

        # Post-execution shortcuts
        shortcut_box = tk.Frame(flood_frame)
        shortcut_box.pack(fill=tk.X, pady=2)
        self.sync_btn = tk.Button(shortcut_box, text="Skip to Synchronize ⚡", font=("Helvetica", 9, "bold"), command=self.skip_to_synchronize, bg="#f39c12", fg="#ffffff", activebackground="#d35400")
        self.sync_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.reset_btn = tk.Button(shortcut_box, text="Reset Engine 🔄", font=("Helvetica", 9, "bold"), command=self.reset_simulation, bg="#7f8c8d", fg="#ffffff", activebackground="#7f8c8d")
        self.reset_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        self.convergence_indicator_lbl = tk.Label(flood_frame, text="🛑 Simulation Not Started", font=("Helvetica", 11, "bold"), bg="#dcdde1", fg="#2c3e50", bd=1, relief=tk.SOLID, pady=4)
        self.convergence_indicator_lbl.pack(fill=tk.X, pady=5)

        tk.Label(flood_frame, text="Link-State Database Sync Matrix (LSDB Status):", font=("Helvetica", 10, "bold"), fg="#34495e").pack(anchor=tk.W, pady=(5, 2))
        self.flood_matrix_text = tk.Text(flood_frame, height=6, font=("Courier New", 9), bg="#f8f9fa", bd=1, relief=tk.SOLID)
        self.flood_matrix_text.pack(fill=tk.X)

        self.log_notebook_frame = ttk.Notebook(flood_frame)
        self.log_notebook_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.tab_commentary_container = tk.Frame(self.log_notebook_frame)
        self.tab_metrics_container = tk.Frame(self.log_notebook_frame)
        
        self.log_notebook_frame.add(self.tab_commentary_container, text=" Global Commentary Log ")
        self.log_notebook_frame.add(self.tab_metrics_container, text=" Convergence Log ")

        scrollbar_f = tk.Scrollbar(self.tab_commentary_container)
        scrollbar_f.pack(side=tk.RIGHT, fill=tk.Y)
        self.flood_log = tk.Text(self.tab_commentary_container, wrap=tk.WORD, font=("Helvetica", 9), bg="#efeef3", bd=0, padx=5, pady=5, yscrollcommand=scrollbar_f.set)
        self.flood_log.pack(fill=tk.BOTH, expand=True)
        scrollbar_f.config(command=self.flood_log.yview)

        scrollbar_c = tk.Scrollbar(self.tab_metrics_container)
        scrollbar_c.pack(side=tk.RIGHT, fill=tk.Y)
        self.convergence_log_box = tk.Text(self.tab_metrics_container, wrap=tk.WORD, font=("Courier New", 9), bg="#1e272e", fg="#ffffff", bd=0, padx=5, pady=5, yscrollcommand=scrollbar_c.set)
        self.convergence_log_box.pack(fill=tk.BOTH, expand=True)
        scrollbar_c.config(command=self.convergence_log_box.yview)

        self.flood_log.tag_config("init", foreground="#7f8c8d")
        self.flood_log.tag_config("hello_tx", foreground="#0984e3", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("hello_rx", foreground="#00b894", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("sent", foreground="#1e3799", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("received", foreground="#218c74", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("process", foreground="#d35400")
        self.flood_log.tag_config("dropped", foreground="#c0392b", font=("Helvetica", 9, "italic"))
        self.flood_log.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))
        self.flood_log.tag_config("converged", foreground="#1b1464", background="#fff200", font=("Helvetica", 9, "bold"))

        self.convergence_log_box.tag_config("INITIAL", foreground="#2ecc71", font=("Courier New", 9, "bold"))
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

        self.local_router_log_box.tag_config("init", foreground="#7f8c8d")
        self.local_router_log_box.tag_config("hello_tx", foreground="#0984e3", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("hello_rx", foreground="#00b894", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("sent", foreground="#1e3799", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("received", foreground="#218c74", font=("Helvetica", 9, "bold"))
        self.local_router_log_box.tag_config("process", foreground="#d35400")
        self.local_router_log_box.tag_config("dropped", foreground="#c0392b", font=("Helvetica", 9, "italic"))
        self.local_router_log_box.tag_config("db_update", foreground="#8e44ad", font=("Helvetica", 9, "bold"))

        self.table_header_lbl = tk.Label(inspect_frame, text="aospf Routing Table (Based on Learned LSAs): Router A", font=("Helvetica", 10, "bold"), fg="#1b5c8f")
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
        self.canvas_f.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig_f.canvas.mpl_connect('button_press_event', self.on_graph_clicked)

    # -------------------------------------------------------
    # NODE SELECTION VS LINK TOGGLE DISRUPTION CLICK MATRICES
    # -------------------------------------------------------
    def on_graph_clicked(self, event):
        if event.xdata is None or event.ydata is None:
            return

        x0, y0 = event.xdata, event.ydata

        # 1. Evaluate Router Node Selection Target Box
        target_node = None
        min_node_threshold = 0.25 
        closest_node_dist = float('inf')

        for node, (nx_val, ny_val) in self.node_positions.items():
            dist = ((x0 - nx_val)**2 + (y0 - ny_val)**2)**0.5
            if dist < closest_node_dist:
                closest_node_dist = dist
                target_node = node

        if closest_node_dist <= min_node_threshold and target_node is not None:
            self.selected_node = target_node
            if self.simulation_started:
                self.render_all_views()
            else:
                self.render_base_configuration_graph()
            return

        # 2. Evaluate Link Selection Target Box
        target_edge = None
        min_edge_threshold = 0.15
        closest_edge_dist = float('inf')

        for u, v in self.G.edges():
            x1, y1 = self.node_positions[u]
            x2, y2 = self.node_positions[v]
            dx, dy = x2 - x1, y2 - y1
            mag2 = dx*dx + dy*dy
            if mag2 == 0: continue

            t = ((x0 - x1) * dx + (y0 - y1) * dy) / mag2
            t = max(0, min(1, t)) 
            cx, cy = x1 + t * dx, y1 + t * dy

            dist = ((x0 - cx)**2 + (y0 - cy)**2)**0.5
            if dist < closest_edge_dist:
                closest_edge_dist = dist
                target_edge = tuple(sorted((u, v)))

        if closest_edge_dist <= min_edge_threshold and target_edge is not None:
            self.selected_edge = target_edge
            if self.simulation_started:
                self.render_all_views()
            else:
                self.render_base_configuration_graph()

    # -------------------------------------------------------
    # BASE CONFIGURATION VIEW GENERATORS
    # -------------------------------------------------------
    def render_base_configuration_graph(self):
        """Draws the network topology mapping preview in an idle baseline state."""
        self.ax_f.clear()
        
        node_colors = ['#1e3799' if n == self.selected_node else '#dcdde1' for n in sorted(self.G.nodes())]
        
        for u, v in self.G.edges():
            edge_tuple = tuple(sorted((u, v)))
            is_selected = (edge_tuple == self.selected_edge)
            color = '#a29bfe' if is_selected else '#2c3e50'
            width = 6.0 if is_selected else 1.5
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color=color, width=width, ax=self.ax_f)
            
        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=node_colors, node_size=400, edgecolors='#2c3e50', ax=self.ax_f)
        
        for name, (x, y) in self.node_positions.items():
            f_color = 'white' if name == self.selected_node else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=10, fontweight='bold', ha='center', va='center', color=f_color)

        edge_labels = {(u, v): f"C:{d['cost']}|{d['bandwidth'].replace('Mbps','M').replace('Gbps','G').replace('Kbps','K')}|{d['delay']}ms" for u, v, d in self.G.edges(data=True)}
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=edge_labels, font_size=8, font_weight='bold', ax=self.ax_f, rotate=True, bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#b2bec3', alpha=0.85))

        self.fig_f.suptitle("")
        self.ax_f.set_title("aospf Network Topology — Configuration Mode", fontsize=10, fontweight='bold', color="#2c3e50")
        self.ax_f.set_xlim(-2, 20)
        self.ax_f.set_ylim(-1, 19)
        self.ax_f.axis('off')
        self.canvas_f.draw()

        self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
        self.delay_change_combo.config(state="disabled")
        
        self.packet_header_lbl.config(text=f"LSA Packet Structure Data: Router {self.selected_node}")
        self.local_log_header_lbl.config(text=f"Contextual Local Port Transmissions Log for Router {self.selected_node}:")
        self.table_header_lbl.config(text=f"aospf Routing Table (Simulation Offline): Router {self.selected_node}")

    # -------------------------------------------------------
    # ACTIVE RUNTIME ROUTING COMPILATION TREE
    # -------------------------------------------------------
    def update_text_panels_data(self):
        target = self.selected_node
        current_clock_time = self.current_time_ms
        state = self.timeline_states[current_clock_time]
        
        # 1. Evaluate Dynamic Link Disruption Action Panel Controls
        if self.selected_edge is None:
            self.link_toggle_btn.config(text="Select a Link on Map", state="disabled", bg="#7f8c8d")
            self.delay_change_combo.config(state="disabled")
        else:
            u, v = self.selected_edge
            self.delay_change_combo.config(state="readonly")
            
            current_delay_value = state["get_delay_func"](u, v, current_clock_time)
            self.delay_change_combo.set(str(current_delay_value))
            
            if self.selected_edge in state['broken_links']:
                self.link_toggle_btn.config(text=f"Enable Link {u}-{v} 🟢", state="normal", bg="#27ae60", fg="#ffffff")
            else:
                self.link_toggle_btn.config(text=f"Disable Link {u}-{v} 🔴", state="normal", bg="#c0392b", fg="#ffffff")

        # 2. Dynamic Convergence Presentation Engine Supporting the Three Protocol States
        if state["is_true_converged"]:
            self.convergence_indicator_lbl.config(
                text=f"🟢 Topology Converged & Stable [Time: {state['true_convergence_time']} ms]", 
                bg="#d4edda", fg="#155724"
            )
        elif state["is_protocol_converged"]:
            if state.get("is_delay_cost_discrepancy", False):
                self.convergence_indicator_lbl.config(
                    text="🟡 Stable but Inaccurate (Delay Cost Discrepancy)", 
                    bg="#fff3cd", fg="#856404"
                )
            else:
                self.convergence_indicator_lbl.config(
                    text="🟡 Stable but Inaccurate", 
                    bg="#fff3cd", fg="#856404"
                )
        else:
            self.convergence_indicator_lbl.config(
                text="⚠️ Syncing Map Data...", 
                bg="#ffeaa7", fg="#d35400"
            )

        known_lsas_payloads = state['lsdb'][target]
        local_topology_view = nx.Graph()
        local_topology_view.add_node(target)
        
        for adv_node, lsa in known_lsas_payloads.items():
            for nbr, cost in lsa['neighbors'].items():
                local_topology_view.add_edge(adv_node, nbr, weight=cost)
        
        lengths, paths = {}, {}
        try:
            lengths = nx.single_source_dijkstra_path_length(local_topology_view, target)
            paths = nx.single_source_dijkstra_path(local_topology_view, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        self.packet_header_lbl.config(text=f"LSA Packet Structure Data: Router {target}")
        self.local_log_header_lbl.config(text=f"Contextual Local Port Transmissions Log for Router {target}:")
        self.table_header_lbl.config(text=f"aospf Routing Table ({current_clock_time} ms Database Snapshot): Router {target}")
        
        self.lsa_view_box.delete('1.0', tk.END)
        if target in known_lsas_payloads:
            active_lsa = known_lsas_payloads[target]
            self.lsa_view_box.insert(tk.END, f"• Source ID: Router_{target} | Seq: {active_lsa['sequence_num']} | TTL: {active_lsa['ttl']}\n")
            self.lsa_view_box.insert(tk.END, "• Advertised Metric Boundaries (Operational Neighbors Only):\n")
            costs = [f"Link {target}->{k} (Cost: {v})" for k, v in active_lsa['neighbors'].items()]
            self.lsa_view_box.insert(tk.END, "  " + (", ".join(costs) if costs else "None (Interfaces Down)"))
        else:
            self.lsa_view_box.insert(tk.END, f"• Source ID: Router_{target} | Seq: -- | Status: DOWN\nNo LSA data generated or stored inside local workspace.")

        # Render Log Traces
        self.local_router_log_box.config(state=tk.NORMAL)
        self.local_router_log_box.delete('1.0', tk.END)
        any_local_events = False
        for log_time, narrative_text, log_type in self.router_events[target]:
            if log_time <= current_clock_time:
                any_local_events = True
                self.local_router_log_box.insert(tk.END, f"[{log_time} ms] {narrative_text}\n", log_type)
        if not any_local_events:
            self.local_router_log_box.insert(tk.END, "No local port interface transitions recorded yet.", "init")
        self.local_router_log_box.config(state=tk.DISABLED)
        self.local_router_log_box.see(tk.END)

        # Render Active Routing Tables
        self.table_view_box.delete('1.0', tk.END)
        header = f"{'Destination':<12} | {'Metric Cost':<11} | {'Next Hop':<9} | {'Computed Path Vector':<20}\n"
        self.table_view_box.insert(tk.END, header)
        self.table_view_box.insert(tk.END, f"{'-'*64}\n")

        for dest in sorted(list(local_topology_view.nodes())):
            if dest == target: continue
            if dest in paths:
                cost_metric = str(lengths[dest])
                path_vector = paths[dest]
                next_hop_node = path_vector[1] if len(path_vector) > 1 else dest
                row_line = f"Network {dest:<4} | {cost_metric:<11} | Router {next_hop_node:<2} | {' -> '.join(path_vector)}\n"
                self.table_view_box.insert(tk.END, row_line)

    def next_timeline_step(self):
        step = int(self.step_combo.get())
        target = self.current_time_ms + step
        while len(self.timeline_states) <= target:
            next(self.sim_generator)
        self.current_time_ms = target
        self.render_all_views()

    def prev_timeline_step(self):
        step_delta = int(self.step_combo.get())
        if self.current_time_ms > 0:
            self.current_time_ms = max(0, self.current_time_ms - step_delta)
            self.render_all_views()

    def render_all_views(self):
        self.update_text_panels_data()
        self.render_flooding_state_view()

    # -------------------------------------------------------
    # Matplotlib Graph Visualization Pipelines
    # -------------------------------------------------------
    def render_flooding_state_view(self):
        self.ax_f.clear()
        current_clock_time = self.current_time_ms
        state = self.timeline_states[current_clock_time]

        self.flood_log.config(state=tk.NORMAL)
        self.flood_log.delete('1.0', tk.END)
        for entry in self.logs_database:
            if entry["time"] <= current_clock_time:
                self.flood_log.insert(tk.END, f"[{entry['time']} ms] {entry['text']}\n", entry["type"])
        self.flood_log.config(state=tk.DISABLED)
        self.flood_log.see(tk.END)

        # Populate the historical timeline values inside the Convergence Log Tab
        self.convergence_log_box.config(state=tk.NORMAL)
        self.convergence_log_box.delete('1.0', tk.END)
        any_metrics_found = False
        for item in self.convergence_metrics_database:
            if item["time"] <= current_clock_time:
                any_metrics_found = True
                self.convergence_log_box.insert(tk.END, f"[{item['time']} ms] {item['text']}\n", item["type"])
        if not any_metrics_found:
            self.convergence_log_box.insert(tk.END, "No stabilization transitions or re-convergence logs calculated up to this millisecond boundary.")
        self.convergence_log_box.config(state=tk.DISABLED)
        self.convergence_log_box.see(tk.END)

        self.flood_matrix_text.delete('1.0', tk.END)
        self.flood_matrix_text.insert(tk.END, f"Node | Learned Processed LSAs Database Map\n{'-'*45}\n")
        for node, contents_dict in sorted(state['lsdb'].items()):
            contents_str = ", ".join(sorted(list(contents_dict.keys())))
            self.flood_matrix_text.insert(tk.END, f"  {node}  | {{{contents_str}}}\n")

        # Set synchronization color layouts
        node_colors = []
        total_nodes_count = len(self.G.nodes())
        for n in sorted(self.G.nodes()):
            if n == self.selected_node:
                node_colors.append('#1e3799') 
            elif len(state['lsdb'][n]) == total_nodes_count:
                node_colors.append('#2ecc71') 
            elif len(state['lsdb'][n]) > 0:
                node_colors.append('#e84118') 
            else:
                node_colors.append('#dcdde1') 

        tx_edges = set()
        edge_colors_map = {}
        for u, v, t_start, t_end, pkt_type in state['active_links']:
            edge_tuple = tuple(sorted((u, v)))
            tx_edges.add(edge_tuple)
            edge_colors_map[edge_tuple] = '#00b894' if pkt_type == "HELLO_ARRIVE" else '#f1c40f'

        for u, v in self.G.edges():
            edge_tuple = tuple(sorted((u, v)))
            is_physically_broken = edge_tuple in state['broken_links']
            is_active_wave = edge_tuple in tx_edges
            is_selected_link = (edge_tuple == self.selected_edge)
            
            if is_physically_broken:
                if state['adj_states'][u][v] == "DOWN" or state['adj_states'][v][u] == "DOWN":
                    color = '#b2bec3' 
                    style = 'dotted'
                    width = 2.0
                else:
                    color = '#e67e22' 
                    style = 'dashed'
                    width = 3.5
            else:
                color = edge_colors_map[edge_tuple] if is_active_wave else '#2c3e50'
                width = 5.0 if is_active_wave else 1.5
                style = 'solid'
            
            if is_selected_link:
                nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color='#a29bfe', width=8.0, alpha=0.6, ax=self.ax_f)
                
            nx.draw_networkx_edges(self.G, self.node_positions, edgelist=[(u, v)], edge_color=color, width=width, style=style, ax=self.ax_f)

        nx.draw_networkx_nodes(self.G, self.node_positions, node_color=node_colors, node_size=400, edgecolors='#2c3e50', ax=self.ax_f)
        for name, (x, y) in self.node_positions.items():
            f_color = 'white' if name == self.selected_node or len(state['lsdb'][name]) > 0 else '#2c3e50'
            self.ax_f.text(x, y, name, fontsize=10, fontweight='bold', ha='center', va='center', color=f_color)

        edge_labels = {}
        for u, v, d in self.G.edges(data=True):
            edge_tuple = tuple(sorted((u, v)))
            if edge_tuple in state['broken_links']:
                status_text = "TO" if (state['adj_states'][u][v] == "DOWN" or state['adj_states'][v][u] == "DOWN") else "HD"
            else:
                # aospf cost lookup
                active_cost_render = state["advertised_costs"][u][v]
                status_text = f"C:{active_cost_render}"
                
            active_delay_render = state["get_delay_func"](u, v, current_clock_time)
            bw = self.original_edges_data.get(tuple(sorted((u,v))), {}).get('bandwidth', '')
            bw_short = bw.replace('Mbps','M').replace('Gbps','G').replace('Kbps','K')
            edge_labels[(u, v)] = f"{status_text}|{bw_short}|{active_delay_render}ms"
        nx.draw_networkx_edge_labels(self.G, self.node_positions, edge_labels=edge_labels, font_size=8, font_weight='bold', ax=self.ax_f, rotate=True, bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#b2bec3', alpha=0.85))

        self.ax_f.set_title(f"Asynchronous aospf Flooding Clock: {current_clock_time} ms", fontsize=10, fontweight='bold', color="#2c3e50")
        self.ax_f.set_xlim(-2, 20)
        self.ax_f.set_ylim(-1, 19)
        self.ax_f.axis('off')
        self.canvas_f.draw()

if __name__ == '__main__':
    window_root = tk.Tk()
    application = aospfAsynchronousWorkspaceDashboard(window_root)
    window_root.mainloop()