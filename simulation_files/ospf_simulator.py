import tkinter as tk
from tkinter import ttk, messagebox
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading
from datetime import datetime
import random
import sys

class OSPFSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive OSPF Protocol Simulator - Adjustable Network")
        self.root.geometry("1400x900")

        # Handle window closure
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Network graph
        self.G = nx.Graph()

        # Track failed links
        self.failed_links = set()
        
        # Store routing tables for all routers
        self.routing_tables = {}
        
        # Convergence tracking
        self.is_converging = False
        self.convergence_log = []
        
        # Network configuration
        self.topology_type = "custom"  
        self.num_routers = 6
        self.network_density = 0.3  
        
        # UI setup
        self.setup_ui()

        # Create initial topology but DON'T compute routing tables automatically
        self.create_default_topology()
        self.update_ui_after_network_change(initial=True)

    def on_closing(self):
        """Cleanly close the application and kill the process"""
        self.is_converging = False 
        self.root.quit() # Stop mainloop
        self.root.destroy() # Destroy widgets
        sys.exit(0) # Kill script process

    # -------------------------------------------------------
    # Network Topology Generators
    # -------------------------------------------------------
    def create_default_topology(self):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {} 
        
        edges = [
            ('R1', 'R2', 2), ('R1', 'R3', 5), ('R2', 'R3', 1),
            ('R2', 'R4', 2), ('R3', 'R5', 3), ('R4', 'R5', 1),
            ('R4', 'R6', 4), ('R5', 'R6', 2)
        ]
        for u, v, w in edges:
            self.G.add_edge(u, v, weight=w, active=True)
    
    def create_mesh_topology(self, n_routers):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {}
        routers = [f'R{i}' for i in range(1, n_routers + 1)]
        for i in range(len(routers)):
            for j in range(i + 1, len(routers)):
                self.G.add_edge(routers[i], routers[j], weight=random.randint(1, 10), active=True)
    
    def create_star_topology(self, n_routers):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {}
        center = 'R1'
        for i in range(2, n_routers + 1):
            self.G.add_edge(center, f'R{i}', weight=random.randint(1, 5), active=True)
    
    def create_ring_topology(self, n_routers):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {}
        routers = [f'R{i}' for i in range(1, n_routers + 1)]
        for i in range(len(routers)):
            self.G.add_edge(routers[i], routers[(i + 1) % len(routers)], weight=random.randint(1, 10), active=True)
            if n_routers > 4 and i < len(routers) - 2:
                self.G.add_edge(routers[i], routers[i + 2], weight=random.randint(1, 10), active=True)
    
    def create_tree_topology(self, n_routers):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {}
        for i in range(1, n_routers + 1):
            for child in [2*i, 2*i+1]:
                if child <= n_routers:
                    self.G.add_edge(f'R{i}', f'R{child}', weight=random.randint(1, 8), active=True)
    
    def create_random_topology(self, n_routers, density=0.3):
        self.G.clear()
        self.failed_links.clear()
        self.routing_tables = {}
        routers = [f'R{i}' for i in range(1, n_routers + 1)]
        possible = [(routers[i], routers[j]) for i in range(len(routers)) for j in range(i+1, len(routers))]
        selected = random.sample(possible, min(int(len(possible)*density), len(possible)))
        for u, v in selected:
            self.G.add_edge(u, v, weight=random.randint(1, 10), active=True)
        if not nx.is_connected(self.G): self.make_network_connected()

    def make_network_connected(self):
        while not nx.is_connected(self.G):
            comps = list(nx.connected_components(self.G))
            u, v = random.choice(list(comps[0])), random.choice(list(comps[1]))
            self.G.add_edge(u, v, weight=random.randint(1, 10), active=True)

    # -------------------------------------------------------
    # OSPF Core Logic
    # -------------------------------------------------------
    def compute_all_routing_tables(self):
        active_graph = self.get_active_graph()
        self.routing_tables = {}
        for router in self.G.nodes():
            if router in active_graph:
                try:
                    paths = nx.single_source_dijkstra_path(active_graph, router)
                    costs = nx.single_source_dijkstra_path_length(active_graph, router)
                    self.routing_tables[router] = {
                        dest: {'next_hop': path[1] if len(path) > 1 else None, 'cost': costs[dest], 'path': path}
                        for dest, path in paths.items() if dest != router
                    }
                except: self.routing_tables[router] = {}
            else: self.routing_tables[router] = {}

    def get_active_graph(self):
        active_graph = nx.Graph()
        for u, v, data in self.G.edges(data=True):
            if data.get('active', True):
                active_graph.add_edge(u, v, weight=data['weight'])
        return active_graph

    # -------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.topology_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.topology_frame, text="Network Topology")
        self.routing_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.routing_frame, text="Routing Tables")
        self.convergence_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.convergence_frame, text="Convergence Log")
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Network Config")
        
        self.setup_topology_tab()
        self.setup_routing_tab()
        self.setup_convergence_tab()
        self.setup_config_tab()

    def setup_topology_tab(self):
        control_frame = tk.Frame(self.topology_frame, padx=10, pady=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)
        graph_frame = tk.Frame(self.topology_frame)
        graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(control_frame, text="OSPF Routing", font=("Arial", 16, "bold")).pack(pady=10)
        tk.Label(control_frame, text="Source Router").pack()
        self.source_combo = ttk.Combobox(control_frame)
        self.source_combo.pack(pady=5)

        tk.Button(control_frame, text="Run OSPF", command=self.run_ospf, bg="#4CAF50", fg="white", width=20).pack(pady=10)
        tk.Label(control_frame, text="Link Failure Simulation", font=("Arial", 14, "bold")).pack(pady=15)
        self.link_var = tk.StringVar()
        self.link_combo = ttk.Combobox(control_frame, textvariable=self.link_var, width=25)
        self.link_combo.pack(pady=5)

        tk.Button(control_frame, text="Fail Link", command=self.fail_link, bg="#E53935", fg="white", width=20).pack(pady=5)
        tk.Button(control_frame, text="Recover Link", command=self.recover_link, bg="#1E88E5", fg="white", width=20).pack(pady=5)
        
        self.network_info_text = tk.Text(control_frame, width=45, height=8)
        self.network_info_text.pack(pady=10)
        
        tk.Button(control_frame, text="Reset Network", command=self.reset_network, bg="#6A1B9A", fg="white", width=20).pack(pady=10)
        self.output_text = tk.Text(control_frame, width=45, height=15)
        self.output_text.pack(pady=5)
        
        self.status_label = tk.Label(control_frame, text="Ready", font=("Arial", 10), fg="green")
        self.status_label.pack(pady=5)
        self.convergence_indicator = tk.Label(control_frame, text="⚫ Not Converging", font=("Arial", 10), fg="gray")
        self.convergence_indicator.pack(pady=5)

        self.fig, self.ax = plt.subplots(figsize=(9, 7))
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def setup_config_tab(self):
        config_frame = tk.Frame(self.config_frame, padx=20, pady=20)
        config_frame.pack(fill=tk.BOTH, expand=True)
        self.topology_var = tk.StringVar(value="custom")
        topology_sub = tk.Frame(config_frame)
        topology_sub.pack(pady=5)
        for t in ["custom", "mesh", "star", "ring", "tree", "random"]:
            tk.Radiobutton(topology_sub, text=t.capitalize(), variable=self.topology_var, value=t).pack(side=tk.LEFT, padx=5)
        
        self.router_count_var = tk.IntVar(value=6)
        tk.Scale(config_frame, from_=3, to=20, orient=tk.HORIZONTAL, variable=self.router_count_var, length=300).pack(pady=5)
        self.density_var = tk.DoubleVar(value=0.3)
        tk.Scale(config_frame, from_=0.1, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.density_var, length=300).pack(pady=5)
        
        tk.Button(config_frame, text="Create Network", command=self.create_network, bg="#4CAF50", fg="white", width=20).pack(pady=20)
        self.ensure_connected_var = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Ensure Connectivity", variable=self.ensure_connected_var).pack()

    def setup_routing_tab(self):
        paned = tk.PanedWindow(self.routing_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        router_frame = tk.Frame(paned, width=200)
        paned.add(router_frame)
        self.router_listbox = tk.Listbox(router_frame)
        self.router_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.router_listbox.bind('<<ListboxSelect>>', self.on_router_select)
        
        table_frame = tk.Frame(paned)
        paned.add(table_frame)
        self.routing_tree = ttk.Treeview(table_frame, columns=('Destination', 'Next Hop', 'Cost', 'Path'), show='headings')
        for col in ('Destination', 'Next Hop', 'Cost', 'Path'): self.routing_tree.heading(col, text=col)
        self.routing_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def setup_convergence_tab(self):
        cf = tk.Frame(self.convergence_frame, padx=10, pady=10)
        cf.pack(side=tk.TOP, fill=tk.X)
        tk.Button(cf, text="Simulate Random Change", command=self.simulate_network_change, bg="#FF9800", fg="white", width=25).pack(pady=5)
        self.convergence_text = tk.Text(self.convergence_frame, wrap=tk.WORD, font=("Courier", 10))
        self.convergence_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # -------------------------------------------------------
    # Convergence and Run Logic
    # -------------------------------------------------------
    def run_ospf(self):
        source = self.source_combo.get()
        if not source:
            messagebox.showwarning("Warning", "Please select a source router.")
            return
        self.simulate_convergence(f"SPF Calculation requested from {source}")

    def simulate_convergence(self, event_description):
        if self.is_converging: return
        self.is_converging = True
        self.convergence_indicator.config(text="🟡 Converging...", fg="orange")
        thread = threading.Thread(target=self._convergence_process, args=(event_description,))
        thread.daemon = True
        thread.start()

    def _convergence_process(self, event_description):
        start_perf = time.perf_counter()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Safety check: if GUI was closed, stop thread
        if not self.is_converging: return
        self.root.after(0, self.update_convergence_display, f"\n{'='*60}\n[{timestamp}] START: {event_description}\n")

        steps = [
            ("🔍 Detecting Network Change...", 0.2, 0.4),
            ("📢 Generating Link State Advertisement...", 0.3, 0.5),
            ("🌊 Flooding LSA to neighbors...", 0.4, 0.7),
            ("💾 Updating Link State Database...", 0.2, 0.3),
            ("🧮 Running Dijkstra SPF Algorithm...", 0.5, 0.8),
            ("📋 Refreshing Routing Tables...", 0.2, 0.3)
        ]

        for step_text, min_t, max_t in steps:
            if not self.is_converging: return # Stop if closed
            curr_ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.root.after(0, self.update_convergence_display, f"[{curr_ts}] {step_text}\n")
            time.sleep(random.uniform(min_t, max_t))

        self.compute_all_routing_tables()
        end_perf = time.perf_counter()
        total_time = end_perf - start_perf
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        final_msg = f"[{timestamp}] ✅ CONVERGED in {total_time:.4f} seconds\n{'='*60}\n"
        
        if self.is_converging:
            self.root.after(0, self.update_convergence_display, final_msg)
            self.root.after(0, self.post_convergence_ui_update, total_time)
        self.is_converging = False

    def post_convergence_ui_update(self, total_time):
        if not self.root.winfo_exists(): return
        self.update_routing_tab_display()
        self.display_all_routing_tables()
        self.convergence_indicator.config(text="✅ Converged", fg="green")
        self.status_label.config(text=f"SPF Complete ({total_time:.2f}s)", fg="green")
        src = self.source_combo.get()
        if src in self.G:
            active_g = self.get_active_graph()
            if src in active_g:
                paths = nx.single_source_dijkstra_path(active_g, src)
                self.draw_graph(paths)

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def update_ui_after_network_change(self, initial=False):
        nodes = list(self.G.nodes())
        self.source_combo['values'] = nodes
        if nodes: self.source_combo.current(0)
        self.update_link_combo()
        self.update_network_info()
        self.draw_graph()
        self.status_label.config(text="Network Ready. Click 'Run OSPF' to converge.", fg="blue")
        if not initial:
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, "Topology changed. Routing tables cleared.\nClick 'Run OSPF' to recalculate paths.")

    def create_network(self):
        n, t = self.router_count_var.get(), self.topology_var.get()
        if t == "custom": self.create_default_topology()
        elif t == "mesh": self.create_mesh_topology(n)
        elif t == "star": self.create_star_topology(n)
        elif t == "ring": self.create_ring_topology(n)
        elif t == "tree": self.create_tree_topology(n)
        elif t == "random": self.create_random_topology(n, self.density_var.get())
        if self.ensure_connected_var.get(): self.make_network_connected()
        self.update_ui_after_network_change()

    def get_link_list(self): return [f"{u}-{v}" for u, v in sorted(self.G.edges())]
    def parse_link(self, txt): return tuple(txt.split('-'))
    def update_link_combo(self):
        links = self.get_link_list()
        self.link_combo['values'] = links
        if links: self.link_combo.current(0)
    
    def update_convergence_display(self, text):
        if self.root.winfo_exists():
            self.convergence_text.insert(tk.END, text)
            self.convergence_text.see(tk.END)

    def update_network_info(self):
        self.network_info_text.delete(1.0, tk.END)
        info = f"Topology: {self.topology_var.get().upper()}\nRouters: {self.G.number_of_nodes()}\nLinks: {self.G.number_of_edges()}\n"
        info += f"Failed Links: {len(self.failed_links)}\nConnected: {nx.is_connected(self.G)}"
        self.network_info_text.insert(1.0, info)

    def draw_graph(self, shortest_paths=None):
        self.ax.clear()
        pos = nx.spring_layout(self.G, seed=42)
        active = [(u, v) for u, v, d in self.G.edges(data=True) if d.get('active', True)]
        failed = [(u, v) for u, v, d in self.G.edges(data=True) if not d.get('active', True)]
        nx.draw_networkx_nodes(self.G, pos, ax=self.ax, node_color='lightblue', node_size=600)
        nx.draw_networkx_labels(self.G, pos, ax=self.ax, font_weight='bold')
        nx.draw_networkx_edges(self.G, pos, edgelist=active, edge_color='green', ax=self.ax, width=2)
        nx.draw_networkx_edges(self.G, pos, edgelist=failed, edge_color='red', style='dashed', ax=self.ax, width=2)
        if shortest_paths:
            path_edges = []
            for p in shortest_paths.values():
                for i in range(len(p)-1): path_edges.append(tuple(sorted((p[i], p[i+1]))))
            nx.draw_networkx_edges(self.G, pos, edgelist=list(set(path_edges)), edge_color='orange', width=4, ax=self.ax)
        self.ax.axis('off'); self.canvas.draw()

    def fail_link(self):
        txt = self.link_combo.get()
        if not txt: return
        u, v = self.parse_link(txt)
        if (u,v) in self.G.edges() and self.G[u][v]['active']:
            self.G[u][v]['active'] = False
            self.failed_links.add((u,v))
            self.draw_graph(); self.update_network_info()
            self.status_label.config(text=f"Link {txt} failed. Recalculate needed.", fg="red")

    def recover_link(self):
        txt = self.link_combo.get()
        if not txt: return
        u, v = self.parse_link(txt)
        if (u,v) in self.G.edges() and not self.G[u][v]['active']:
            self.G[u][v]['active'] = True
            self.failed_links.discard((u,v))
            self.draw_graph(); self.update_network_info()
            self.status_label.config(text=f"Link {txt} recovered. Recalculate needed.", fg="blue")

    def reset_network(self):
        for u, v in self.G.edges(): self.G[u][v]['active'] = True
        self.failed_links.clear()
        self.routing_tables = {}
        self.update_ui_after_network_change()

    def simulate_network_change(self):
        if self.failed_links:
            u, v = list(self.failed_links)[0]
            self.G[u][v]['active'] = True
            self.failed_links.remove((u, v))
            desc = f"Random Recovery: {u}-{v}"
        else:
            active = [(u, v) for u, v, d in self.G.edges(data=True) if d.get('active', True)]
            if not active: return
            u, v = random.choice(active)
            self.G[u][v]['active'] = False
            self.failed_links.add((u, v))
            desc = f"Random Failure: {u}-{v}"
        self.draw_graph(); self.update_network_info()
        self.simulate_convergence(desc)

    def on_router_select(self, event):
        sel = self.router_listbox.curselection()
        if sel:
            router = self.router_listbox.get(sel[0])
            for i in self.routing_tree.get_children(): self.routing_tree.delete(i)
            if router in self.routing_tables:
                for d, info in sorted(self.routing_tables[router].items()):
                    self.routing_tree.insert('', tk.END, values=(d, info['next_hop'] or 'Direct', info['cost'], '->'.join(info['path'])))

    def update_routing_tab_display(self):
        self.router_listbox.delete(0, tk.END)
        for r in sorted(self.G.nodes()): self.router_listbox.insert(tk.END, r)

    def display_all_routing_tables(self):
        self.output_text.delete(1.0, tk.END)
        if not self.routing_tables:
            self.output_text.insert(tk.END, "No routing data. Please click 'Run OSPF'.")
            return
        for r, table in sorted(self.routing_tables.items()):
            self.output_text.insert(tk.END, f"\nRouter {r}\n{'-'*20}\n")
            for d, i in table.items(): self.output_text.insert(tk.END, f"{d}: Cost {i['cost']} via {i['next_hop']}\n")

if __name__ == '__main__':
    root = tk.Tk()
    app = OSPFSimulator(root)
    root.mainloop()