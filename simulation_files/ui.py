import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import networkx as nx

class OSPFSimulatorUI:
    def __init__(self, root, config_info=None, protocol_name="OSPF"):
        self.root = root
        self.protocol_name = protocol_name
        self.root.title(f"{protocol_name} Protocol Simulator - Discrete Event")
        self.root.geometry("1600x950")
        self.root.configure(bg="#f0f0f0")
        
        self.graph_pos = None
        self.matplotlib_fig = None
        self.matplotlib_ax = None
        self.canvas = None
        
        self.create_title_bar(config_info)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.topology_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.topology_frame, text="Network Topology")
        self.setup_topology_tab()
        
        self.routing_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.routing_frame, text="Routing Tables")
        self.setup_routing_tab()
        
        self.create_status_bar()
        
    def create_title_bar(self, config_info):
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=f"[{self.protocol_name}]", font=("Arial", 14, "bold"), bg="#2c3e50", fg="#3498db").pack(side=tk.LEFT, padx=10, pady=10)
        
    def setup_topology_tab(self):
        control_frame = tk.Frame(self.topology_frame, bg="white", width=280)
        control_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Sim Speed
        tk.Label(control_frame, text="Simulation Speed:", font=("Arial", 10, "bold"), bg="white").pack(pady=(10, 0), padx=10, anchor="w")
        self.speed_var = tk.DoubleVar(value=10.0)
        self.speed_slider = tk.Scale(control_frame, from_=0.1, to=100.0, orient=tk.HORIZONTAL, variable=self.speed_var, bg="white", resolution=0.1)
        self.speed_slider.pack(pady=5, padx=10, fill=tk.X)
        
        # Convergence time
        tk.Label(control_frame, text="Convergence Time:", font=("Arial", 9, "bold"), bg="white").pack(pady=(10, 0), padx=10, anchor="w")
        self.est_time_label = tk.Label(control_frame, text="--", font=("Arial", 9), bg="#ecf0f1", fg="#e74c3c", padx=10, pady=5)
        self.est_time_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Link failure control
        tk.Label(control_frame, text="Link Control:", font=("Arial", 10, "bold"), bg="white").pack(pady=(15, 0), padx=10, anchor="w")
        self.link_combo = ttk.Combobox(control_frame, state="readonly", width=20)
        self.link_combo.pack(pady=5, padx=10)
        
        self.fail_link_btn = tk.Button(control_frame, text="✕ Fail Link", bg="#e74c3c", fg="white", font=("Arial", 10, "bold"))
        self.fail_link_btn.pack(pady=5, padx=10, fill=tk.X)
        
        self.recover_link_btn = tk.Button(control_frame, text="✓ Recover Link", bg="#27ae60", fg="white", font=("Arial", 10, "bold"), state="disabled")
        self.recover_link_btn.pack(pady=5, padx=10, fill=tk.X)
        
        self.skip_btn = tk.Button(control_frame, text="⏩ Skip to Converged", bg="#9b59b6", fg="white", font=("Arial", 10, "bold"))
        self.skip_btn.pack(pady=5, padx=10, fill=tk.X)
        
        # Info
        tk.Label(control_frame, text="Network Information", font=("Arial", 10, "bold"), bg="white").pack(pady=(15, 5), padx=10, anchor="w")
        self.info_text = tk.Text(control_frame, height=8, width=28, bg="#ecf0f1", font=("Courier", 9), state="disabled")
        self.info_text.pack(pady=5, padx=10)
        
        self.status_label = tk.Label(control_frame, text="Ready", font=("Arial", 9), bg="white", fg="#27ae60")
        self.status_label.pack(pady=5, padx=10, anchor="w")
        
        self.graph_frame = tk.Frame(self.topology_frame, bg="white")
        self.graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def setup_routing_tab(self):
        list_frame = tk.Frame(self.routing_frame, width=180, bg="white")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        list_frame.pack_propagate(False)
        self.router_listbox = tk.Listbox(list_frame, font=("Arial", 10), bg="#ecf0f1", exportselection=False)
        self.router_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        table_frame = tk.Frame(self.routing_frame, bg="white")
        table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.routing_text = tk.Text(table_frame, font=("Courier", 9), bg="#ecf0f1")
        self.routing_text.pack(fill=tk.BOTH, expand=True)

    def create_status_bar(self):
        status_frame = tk.Frame(self.root, bg="#34495e", height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        self.statusbar_label = tk.Label(status_frame, text="Ready", bg="#34495e", fg="#ecf0f1", font=("Arial", 9))
        self.statusbar_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.sim_time_label = tk.Label(status_frame, text="Sim Time: 0.0s", bg="#34495e", fg="#f1c40f", font=("Arial", 9, "bold"))
        self.sim_time_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
    def get_sim_speed(self):
        return self.speed_var.get()
        
    def get_selected_router(self):
        sel = self.router_listbox.curselection()
        if not sel: return None
        return self.router_listbox.get(sel[0]).split(" ")[0]
        
    def update_sim_time(self, t):
        self.sim_time_label.config(text=f"Sim Time: {t:.1f}s")
        
    def update_topology_info(self, network_info, routers):
        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, "Continuous Event Sim\nRunning...")
        self.info_text.config(state="disabled")
        
    def update_router_list(self, routers):
        self.router_listbox.delete(0, tk.END)
        for router in routers:
            self.router_listbox.insert(tk.END, f"{router.get('id')} - {router.get('name', '')}")
            
    def draw_topology(self, graph):
        if not graph or len(graph.nodes()) == 0: return
        self.graph_pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)
        plt.close('all')
        for widget in self.graph_frame.winfo_children(): widget.destroy()
        
        self.matplotlib_fig, self.matplotlib_ax = plt.subplots(figsize=(9, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.matplotlib_fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.render_continuous(graph, [], 0, None)
        
    def render_continuous(self, graph, packets, sim_time, selected_router):
        if not self.graph_pos: return
        self.matplotlib_ax.clear()
        
        # Calculate shortest path tree if selected
        tree_edges = set()
        if selected_router and selected_router in graph.nodes():
            try:
                paths = nx.shortest_path(graph, source=selected_router, weight='weight')
                for target, path in paths.items():
                    for i in range(len(path)-1):
                        tree_edges.add((path[i], path[i+1]))
                        tree_edges.add((path[i+1], path[i]))
            except: pass
            
        # Draw edges
        regular_edges = []
        highlight_edges = []
        for u, v in graph.edges():
            if (u, v) in tree_edges: highlight_edges.append((u, v))
            else: regular_edges.append((u, v))
            
        if regular_edges:
            nx.draw_networkx_edges(graph, self.graph_pos, edgelist=regular_edges, width=2, alpha=0.6, edge_color="#95a5a6", ax=self.matplotlib_ax)
        if highlight_edges:
            nx.draw_networkx_edges(graph, self.graph_pos, edgelist=highlight_edges, width=3, alpha=0.9, edge_color="#f39c12", ax=self.matplotlib_ax)
            
        nx.draw_networkx_nodes(graph, self.graph_pos, node_color="#3498db", node_size=1500, ax=self.matplotlib_ax)
        nx.draw_networkx_labels(graph, self.graph_pos, font_size=10, font_weight="bold", ax=self.matplotlib_ax)
        
        # Draw packets
        for pkt in packets:
            src = pkt['src']
            dst = pkt['dst']
            start_t = pkt['start_time']
            arr_t = pkt['arrival_time']
            color = pkt.get('color', '#e74c3c')
            
            if src in self.graph_pos and dst in self.graph_pos and arr_t > start_t:
                progress = (sim_time - start_t) / (arr_t - start_t)
                progress = max(0.0, min(1.0, progress))
                
                start_pos = self.graph_pos[src]
                end_pos = self.graph_pos[dst]
                x = start_pos[0] + (end_pos[0] - start_pos[0]) * progress
                y = start_pos[1] + (end_pos[1] - start_pos[1]) * progress
                self.matplotlib_ax.plot(x, y, marker='o', color=color, markersize=8, zorder=6)
                
        self.matplotlib_ax.axis("off")
        self.canvas.draw_idle()
        
    def display_routing_table(self, router_id, routing_table):
        self.routing_text.config(state="normal")
        self.routing_text.delete(1.0, tk.END)
        content = f"Routing Table for {router_id}:\n"
        content += f"{'Destination':<15} {'Next Hop':<15} {'Metric':<10}\n"
        content += "-" * 45 + "\n"
        if routing_table:
            for dest, info in sorted(routing_table.items()):
                cost = info.get('cost', info.get('metric', 0))
                next_hop = info.get('next_hop', dest)
                content += f"{dest+'/32':<15} {next_hop:<15} {cost:<10}\n"
        else:
            content += "No routes calculated yet."
        self.routing_text.insert(tk.END, content)
        self.routing_text.config(state="disabled")
        
    def update_status(self, message, color="green"):
        self.statusbar_label.config(text=message, fg=color)
        
    def update_estimated_convergence_time(self, estimated_time):
        self.est_time_label.config(text=f"{estimated_time:.3f}s", fg="#27ae60")
        
    def show_message(self, title, message, message_type="info"):
        if message_type == "error": messagebox.showerror(title, message)
        elif message_type == "warning": messagebox.showwarning(title, message)
        else: messagebox.showinfo(title, message)
