"""
UI Components for OSPF Protocol Simulator
Provides interface for network visualization and routing table display
"""
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import networkx as nx
import threading
import time


class OSPFSimulatorUI:
    """Main UI for Protocol Simulator"""
    
    def __init__(self, root, config_info=None, protocol_name="OSPF"):
        self.root = root
        self.protocol_name = protocol_name
        self.root.title(f"{protocol_name} Protocol Simulator - Auto-Reload on JSON Change")
        self.root.geometry("1600x950")
        self.root.configure(bg="#f0f0f0")
        
        # Animation state
        self.animation_running = False
        self.animated_packets = []
        self.graph_pos = None
        self.matplotlib_fig = None
        self.matplotlib_ax = None
        self.canvas = None
        self.graph_edges = []
        self.animated_links = set()
        self.protocol_info = None  # Store protocol-specific info
        
        # Title bar
        self.create_title_bar(config_info)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Topology tab
        self.topology_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.topology_frame, text="Network Topology")
        self.setup_topology_tab()
        
        # Routing tables tab
        self.routing_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.routing_frame, text="Routing Tables")
        self.setup_routing_tab()
        
        # Status bar
        self.create_status_bar()
    
    def create_title_bar(self, config_info):
        """Create title bar with network information"""
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        # Protocol name with color coding
        protocol_colors = {
            "OSPF": "#e74c3c",
            "BGP": "#3498db",
            "RIP": "#f39c12",
            "ISIS": "#9b59b6"
        }
        protocol_color = protocol_colors.get(self.protocol_name, "#27ae60")
        
        tk.Label(title_frame, text=f"[{self.protocol_name}]", font=("Arial", 14, "bold"),
                bg="#2c3e50", fg=protocol_color).pack(side=tk.LEFT, padx=10, pady=10)
        
        if config_info:
            title = f"{config_info.get('name', 'Network')} - {config_info.get('num_routers', 0)} Routers"
            description = config_info.get('description', '')
        else:
            title = "Protocol Simulator"
            description = "Loading configuration..."
        
        tk.Label(title_frame, text=title, font=("Arial", 14, "bold"), 
                bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=10, pady=10)
        
        tk.Label(title_frame, text=description, font=("Arial", 10), 
                bg="#2c3e50", fg="#ecf0f1").pack(side=tk.LEFT, padx=10, pady=10)
    
    def setup_topology_tab(self):
        """Setup Network Topology tab"""
        # Control panel on left
        control_frame = tk.Frame(self.topology_frame, bg="white", width=280)
        control_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Title with protocol name
        protocol_colors = {
            "OSPF": "#e74c3c",
            "BGP": "#3498db",
            "RIP": "#f39c12",
            "ISIS": "#9b59b6"
        }
        protocol_color = protocol_colors.get(self.protocol_name, "#27ae60")
        
        protocol_label = tk.Label(control_frame, text=f"{self.protocol_name} Routing Engine", 
                                 font=("Arial", 12, "bold"), bg="white", fg=protocol_color)
        protocol_label.pack(pady=10)
        
        # Source router selection
        tk.Label(control_frame, text="Source Router:", font=("Arial", 10, "bold"),
                bg="white").pack(pady=(10, 0), padx=10, anchor="w")
        self.source_combo = ttk.Combobox(control_frame, state="readonly", width=20)
        self.source_combo.pack(pady=5, padx=10)
        
        # Run Protocol button (with auto-animation)
        self.run_ospf_btn = tk.Button(control_frame, text=f"▶ Run {self.protocol_name}",
                                      bg="#27ae60", fg="white", font=("Arial", 11, "bold"),
                                      cursor="hand2", padx=5, pady=10)
        self.run_ospf_btn.pack(pady=10, padx=10, fill=tk.X)
        
        # Convergence time display
        tk.Label(control_frame, text="Convergence Time:", font=("Arial", 9, "bold"),
                bg="white").pack(pady=(10, 0), padx=10, anchor="w")
        self.est_time_label = tk.Label(control_frame, text="--", font=("Arial", 9),
                                       bg="#ecf0f1", fg="#e74c3c", padx=10, pady=5)
        self.est_time_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Link failure control section
        tk.Label(control_frame, text="Link Control:", font=("Arial", 10, "bold"),
                bg="white").pack(pady=(15, 0), padx=10, anchor="w")
        
        self.link_combo = ttk.Combobox(control_frame, state="readonly", width=20)
        self.link_combo.pack(pady=5, padx=10)
        
        # Fail link button
        self.fail_link_btn = tk.Button(control_frame, text="✕ Fail Link",
                                       bg="#e74c3c", fg="white", font=("Arial", 10, "bold"),
                                       cursor="hand2", padx=5, pady=8)
        self.fail_link_btn.pack(pady=5, padx=10, fill=tk.X)
        
        # Recover link button
        self.recover_link_btn = tk.Button(control_frame, text="✓ Recover Link",
                                          bg="#27ae60", fg="white", font=("Arial", 10, "bold"),
                                          cursor="hand2", padx=5, pady=8, state="disabled")
        self.recover_link_btn.pack(pady=5, padx=10, fill=tk.X)
        
        # Info section
        tk.Label(control_frame, text="Network Information", font=("Arial", 10, "bold"),
                bg="white").pack(pady=(15, 5), padx=10, anchor="w")
        
        self.info_text = tk.Text(control_frame, height=8, width=28, bg="#ecf0f1",
                                font=("Courier", 9), state="disabled")
        self.info_text.pack(pady=5, padx=10)
        
        # Status
        tk.Label(control_frame, text="Status:", font=("Arial", 10, "bold"),
                bg="white").pack(pady=(10, 0), padx=10, anchor="w")
        self.status_label = tk.Label(control_frame, text="Ready", font=("Arial", 9),
                                     bg="white", fg="#27ae60")
        self.status_label.pack(pady=5, padx=10, anchor="w")
        
        # Graph area on right
        self.graph_frame = tk.Frame(self.topology_frame, bg="white")
        self.graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def setup_routing_tab(self):
        """Setup Routing Tables tab with router list and table"""
        # Left panel - router list
        list_frame = tk.Frame(self.routing_frame, width=180, bg="white")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        list_frame.pack_propagate(False)
        
        tk.Label(list_frame, text="Available Routers", font=("Arial", 10, "bold"),
                bg="white").pack(pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.router_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                         font=("Arial", 10), bg="#ecf0f1")
        self.router_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        scrollbar.config(command=self.router_listbox.yview)
        
        # Right panel - routing table
        table_frame = tk.Frame(self.routing_frame, bg="white")
        table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(table_frame, text="Routing Table", font=("Arial", 10, "bold"),
                bg="white").pack(pady=5)
        
        scrollbar2 = ttk.Scrollbar(table_frame)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.routing_text = tk.Text(table_frame, yscrollcommand=scrollbar2.set,
                                   font=("Courier", 9), bg="#ecf0f1")
        self.routing_text.pack(fill=tk.BOTH, expand=True)
        scrollbar2.config(command=self.routing_text.yview)
    
    def create_status_bar(self):
        """Create status bar at bottom"""
        status_frame = tk.Frame(self.root, bg="#34495e", height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.statusbar_label = tk.Label(status_frame, text="Ready | Watching JSON file for changes...",
                                       bg="#34495e", fg="#ecf0f1", font=("Arial", 9))
        self.statusbar_label.pack(side=tk.LEFT, padx=10, pady=5)
    
    def update_topology_info(self, network_info, routers):
        """Update network information display"""
        info_text = self.info_text
        info_text.config(state="normal")
        info_text.delete(1.0, tk.END)
        
        info = f"""Network: {network_info.get('name', 'OSPF Network')}

Version: {network_info.get('version', '1.0')}

Routers: {network_info.get('num_routers', 0)}
Links: {network_info.get('num_links', 0)}

Routers:
"""
        for router in routers:
            info += f"  • {router.get('id')} - {router.get('name', '')}\n"
        
        info_text.insert(tk.END, info)
        info_text.config(state="disabled")
    
    def draw_topology(self, graph, recalculate_pos=True):
        """Draw network topology graph with animation support"""
        if not graph or len(graph.nodes()) == 0:
            return
        
        # Store graph position for animation
        if recalculate_pos or not hasattr(self, 'graph_pos') or self.graph_pos is None:
            self.graph_pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)
        self.graph_edges = list(graph.edges(data=True))
        self.animated_links = set()  # Reset animated links
        
        # Clear previous matplotlib figures
        plt.close('all')
        
        # Clear previous widgets in frame
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
        
        # Create matplotlib figure
        self.matplotlib_fig, self.matplotlib_ax = plt.subplots(figsize=(9, 7), dpi=100)
        ax = self.matplotlib_ax
        
        # Draw static elements
        # Draw edges
        nx.draw_networkx_edges(graph, self.graph_pos, width=2, alpha=0.6, 
                              edge_color="#95a5a6", ax=ax)
        
        # Draw nodes
        nx.draw_networkx_nodes(graph, self.graph_pos, node_color="#3498db", 
                              node_size=1500, ax=ax)
        
        # Draw labels
        nx.draw_networkx_labels(graph, self.graph_pos, font_size=10, font_weight="bold", ax=ax)
        
        # Draw edge weights
        edge_labels = nx.get_edge_attributes(graph, 'weight')
        nx.draw_networkx_edge_labels(graph, self.graph_pos, edge_labels, font_size=8, ax=ax)
        
        ax.set_title("Network Topology (Animation Ready)", fontsize=12, fontweight="bold")
        ax.axis("off")
        plt.tight_layout()
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.matplotlib_fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def animate_protocol_on_topology(self, graph, routers, source_router=None, protocol_info=None):
        """Animate shortest path tree from source router"""
        if not self.graph_pos or not protocol_info:
            return
        
        self.animated_packets = []
        
        if source_router and source_router in graph.nodes():
            try:
                # Calculate shortest paths
                paths = nx.shortest_path(graph, source=source_router, weight='weight')
                distances = nx.single_source_shortest_path_length(graph, source_router)
                
                # Extract all edges that form the shortest path tree
                tree_edges = set()
                for target, path in paths.items():
                    for i in range(len(path)-1):
                        tree_edges.add((path[i], path[i+1]))
                
                # Create animation packets for these edges based on distance from source
                for u, v in tree_edges:
                    dist = distances[u]
                    self.animated_packets.append({
                        'start': u,
                        'end': v,
                        'offset': dist * 0.5,  # Stagger based on hop count
                        'progress': -1,
                        'duration': 1.0
                    })
            except nx.NetworkXNoPath:
                pass
            except Exception as e:
                print(f"Error animating shortest paths: {e}")
        
        # Start animation on main thread using after()
        self.animation_running = True
        self.protocol_info = protocol_info  # Store for display
        start_time = time.time()
        self.root.after(0, self._animate_step, start_time)
    
    def animate_hello_on_topology(self, graph, routers, source_router=None):
        """Animate HELLO messages spreading from source router"""
        if not self.graph_pos:
            return
        
        self.animated_packets = []
        
        if source_router and source_router in graph.nodes():
            # BFS from source router to generate spreading HELLO messages
            from collections import deque
            visited = set()
            queue = deque([(source_router, 0)])  # (router, distance)
            visited.add(source_router)
            offset_counter = 0
            
            while queue:
                current_router, distance = queue.popleft()
                
                # Send HELLO to all neighbors
                for neighbor in graph.neighbors(current_router):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, distance + 1))
                        
                        # Create packets for both directions
                        self.animated_packets.append({
                            'start': current_router,
                            'end': neighbor,
                            'offset': offset_counter * 0.2,  # Stagger by 0.2s
                            'progress': -1,
                            'duration': 1.2
                        })
                        # Return HELLO back
                        self.animated_packets.append({
                            'start': neighbor,
                            'end': current_router,
                            'offset': offset_counter * 0.2 + 0.6,  # Offset for return
                            'progress': -1,
                            'duration': 1.2
                        })
                        offset_counter += 1
        else:
            # If no source router specified, animate all edges (original behavior)
            for i, (src, dest, data) in enumerate(graph.edges(data=True)):
                # Forward direction with staggered offset
                self.animated_packets.append({
                    'start': src,
                    'end': dest,
                    'offset': i * 0.3,  # Stagger start times
                    'progress': -1,
                    'duration': 1.5  # Time to traverse link
                })
                # Backward direction
                self.animated_packets.append({
                    'start': dest,
                    'end': src,
                    'offset': i * 0.3 + 0.75,  # Offset for return
                    'progress': -1,
                    'duration': 1.5
                })
        
        # Start animation on main thread using after()
        self.animation_running = True
        start_time = time.time()
        self.root.after(0, self._animate_step, start_time)
    
    def _animate_step(self, start_time):
        """Animation step called periodically via root.after()"""
        if not self.animation_running:
            return
            
        total_duration = 8  # Total animation duration in seconds
        elapsed = time.time() - start_time
        
        if elapsed < total_duration:
            # Update packet positions based on elapsed time and initial offset
            for packet in self.animated_packets:
                offset = packet.get('offset', 0)  # Initial delay for staggered start
                if elapsed >= offset:
                    packet['progress'] = (elapsed - offset) / packet['duration']
                    # Cap progress at 1.0
                    if packet['progress'] > 1.0:
                        packet['progress'] = 1.0
                        # Add link to animated set when complete
                        self.animated_links.add((packet['start'], packet['end']))
                        self.animated_links.add((packet['end'], packet['start']))
                else:
                    packet['progress'] = -1  # Not started yet
            
            # Redraw
            try:
                self._redraw_topology_with_packets()
                self.canvas.draw()
            except:
                pass
            
            # Schedule next step
            self.root.after(50, self._animate_step, start_time)
        else:
            self.animation_running = False
            # Redraw final state with orange links
            try:
                self._redraw_topology_with_packets(show_packets=False, show_orange_links=True)
                self.canvas.draw()
            except:
                pass
    
    def _redraw_topology_with_packets(self, show_packets=True, show_orange_links=False):
        """Redraw topology with animated packets and edge colors"""
        self.matplotlib_ax.clear()
        
        if not self.graph_pos or not self.graph_edges:
            return
        
        # Create graph for drawing
        graph = nx.Graph()
        for node in self.graph_pos.keys():
            graph.add_node(node)
        for src, dest, data in self.graph_edges:
            graph.add_edge(src, dest, weight=data.get('weight', 1))
        
        # When animation completes, all links become orange
        protocol_colors = {
            'hello': '#e74c3c',          # OSPF - red
            'update': '#3498db',         # BGP - blue
            'distance_vector': '#f39c12',# RIP - orange
            'lsp': '#9b59b6'             # IS-IS - purple
        }
        anim_type = None
        if hasattr(self, 'protocol_info') and self.protocol_info:
            anim_type = self.protocol_info.get('animation_type')

        if show_orange_links:
            # Draw only shortest path edges as orange
            animated_edges = []
            regular_edges = []

            for edge in graph.edges():
                src, dest = edge
                if (src, dest) in self.animated_links or (dest, src) in self.animated_links:
                    animated_edges.append(edge)
                else:
                    regular_edges.append(edge)

            # Draw regular edges (gray)
            if regular_edges:
                nx.draw_networkx_edges(graph, self.graph_pos, edgelist=regular_edges,
                                      width=2, alpha=0.6, edge_color="#95a5a6",
                                      ax=self.matplotlib_ax)

            # Draw animated edges as orange
            if animated_edges:
                nx.draw_networkx_edges(graph, self.graph_pos, edgelist=animated_edges,
                                      width=2.5, alpha=0.95, edge_color="#ff9800",
                                      ax=self.matplotlib_ax)
        else:
            # Draw edges with different colors based on animation state
            animated_edges = []
            regular_edges = []

            for edge in graph.edges():
                src, dest = edge
                if (src, dest) in self.animated_links or (dest, src) in self.animated_links:
                    animated_edges.append(edge)
                else:
                    regular_edges.append(edge)

            # Draw regular edges (gray)
            if regular_edges:
                nx.draw_networkx_edges(graph, self.graph_pos, edgelist=regular_edges,
                                      width=2, alpha=0.6, edge_color="#95a5a6",
                                      ax=self.matplotlib_ax)

            # Choose a highlight color for animated edges based on protocol
            highlight_color = protocol_colors.get(anim_type, '#2ecc71')

            # Draw animated edges in protocol color (distinct during animation)
            if animated_edges:
                nx.draw_networkx_edges(graph, self.graph_pos, edgelist=animated_edges,
                                      width=3.0, alpha=0.9, edge_color=highlight_color,
                                      ax=self.matplotlib_ax)
        
        # Draw nodes
        nx.draw_networkx_nodes(graph, self.graph_pos, node_color="#3498db", 
                              node_size=1500, ax=self.matplotlib_ax)
        
        # Draw labels
        nx.draw_networkx_labels(graph, self.graph_pos, font_size=10, font_weight="bold", 
                               ax=self.matplotlib_ax)
        
        # Draw edge weights
        edge_labels = nx.get_edge_attributes(graph, 'weight')
        nx.draw_networkx_edge_labels(graph, self.graph_pos, edge_labels, font_size=8, 
                                    ax=self.matplotlib_ax)
        
        # Draw animated packets with protocol-specific marker color
        if show_packets:
            # packet color mapping
            packet_colors = {
                'hello': 'r',
                'update': 'b',
                'distance_vector': '#ff8800',
                'lsp': '#9b59b6'
            }
            packet_color = packet_colors.get(anim_type, 'r')

            for packet in self.animated_packets:
                progress = packet.get('progress', -1)
                if 0 <= progress <= 1:
                    # Interpolate position
                    start_pos = self.graph_pos[packet['start']]
                    end_pos = self.graph_pos[packet['end']]
                    x = start_pos[0] + (end_pos[0] - start_pos[0]) * progress
                    y = start_pos[1] + (end_pos[1] - start_pos[1]) * progress

                    # Draw packet marker (color depends on protocol)
                    self.matplotlib_ax.plot(x, y, marker='o', color=packet_color, markersize=10, zorder=6)
        
        # Build title with protocol-specific information
        if hasattr(self, 'protocol_info') and self.protocol_info:
            message_type = self.protocol_info.get('message_type', 'Messages')
            if show_packets:
                title = f"Network Topology (Red Dots = {message_type})"
            else:
                title = f"Network Topology (Orange Links = Protocol Paths Used)"
        else:
            title = "Network Topology (Red Dots = Messages)"
            if show_orange_links:
                title = "Network Topology (Orange Links = Paths Used)"
        
        self.matplotlib_ax.set_title(title, fontsize=12, fontweight="bold")
        self.matplotlib_ax.axis("off")
    
    def update_router_list(self, routers):
        """Update router listbox"""
        self.router_listbox.delete(0, tk.END)
        for router in routers:
            self.router_listbox.insert(tk.END, f"{router.get('id')} - {router.get('name', '')}")
    
    def display_routing_table(self, router_id, routing_table):
        """Display routing table for selected router with protocol-specific format"""
        self.routing_text.config(state="normal")
        self.routing_text.delete(1.0, tk.END)
        
        protocol = self.protocol_name.upper()
        
        def parse_info(info, dest):
            if isinstance(info, dict):
                return info.get('cost', 0), info.get('next_hop', dest), info.get('as_path', '')
            return info, dest, ''
        
        if protocol == "OSPF":
            content = f"OSPF Routing Table for {router_id}:\n"
            content += "Codes: O - OSPF, IA - OSPF inter area, E1 - OSPF external type 1\n\n"
            content += f"{'Network':<15} {'Next Hop':<15} {'Metric':<10}\n"
            content += "-" * 45 + "\n"
            if routing_table:
                for dest, info in sorted(routing_table.items()):
                    cost, next_hop, _ = parse_info(info, dest)
                    content += f"O   {dest+'/32':<11} via {next_hop:<11} {cost:<10}\n"
                    
        elif protocol == "BGP":
            content = f"BGP Routing Table for {router_id}:\n"
            content += f"Status codes: s suppressed, d damped, h history, * valid, > best, i - internal\n\n"
            content += f"{'Network':<15} {'Next Hop':<15} {'Metric':<8} {'AS Path'}\n"
            content += "-" * 60 + "\n"
            if routing_table:
                for dest, info in sorted(routing_table.items()):
                    cost, next_hop, as_path = parse_info(info, dest)
                    if not as_path: as_path = "Local"
                    content += f"*>i {dest+'/32':<11} {next_hop:<15} {cost:<8} {as_path} i\n"
                    
        elif protocol == "RIP":
            content = f"RIP Routing Table for {router_id}:\n"
            content += "Codes: R - RIP\n\n"
            content += f"{'Network':<15} {'Next Hop':<15} {'Hops':<8} {'Timer'}\n"
            content += "-" * 55 + "\n"
            if routing_table:
                for dest, info in sorted(routing_table.items()):
                    cost, next_hop, _ = parse_info(info, dest)
                    status = "00:00:15" if cost <= 15 else "down"
                    content += f"R   {dest+'/32':<11} via {next_hop:<11} {cost:<8} {status}\n"
                    
        elif protocol == "ISIS":
            content = f"IS-IS Routing Table for {router_id}:\n"
            content += "Codes: i - IS-IS, L1 - Level-1, L2 - Level-2\n\n"
            content += f"{'Network':<15} {'Next Hop':<15} {'Metric':<10}\n"
            content += "-" * 45 + "\n"
            if routing_table:
                for i, (dest, info) in enumerate(sorted(routing_table.items())):
                    cost, next_hop, _ = parse_info(info, dest)
                    level = "L2" if i % 3 == 0 else "L1"
                    content += f"i {level} {dest+'/32':<10} via {next_hop:<11} {cost:<10}\n"
        
        else:
            content = f"Routing Table for {router_id}:\n"
            content += f"{'Destination':<15} {'Metric':<10}\n"
            content += "-" * 25 + "\n"
            if routing_table:
                for dest, info in sorted(routing_table.items()):
                    cost, _, _ = parse_info(info, dest)
                    content += f"{dest:<15} {cost:<10}\n"
        
        if not routing_table:
            content += "No routes calculated yet."
        
        self.routing_text.insert(tk.END, content)
        self.routing_text.config(state="disabled")
    
    def update_status(self, message, color="green"):
        """Update status bar"""
        self.statusbar_label.config(text=message, fg=color)
        self.root.update()
    
    def update_estimated_convergence_time(self, estimated_time):
        """Update estimated convergence time display"""
        time_text = f"{estimated_time:.3f}s"
        self.est_time_label.config(text=time_text, fg="#e74c3c")
        self.root.update()
    
    def show_message(self, title, message, message_type="info"):
        """Show message dialog"""
        if message_type == "error":
            messagebox.showerror(title, message)
        elif message_type == "warning":
            messagebox.showwarning(title, message)
        else:
            messagebox.showinfo(title, message)
