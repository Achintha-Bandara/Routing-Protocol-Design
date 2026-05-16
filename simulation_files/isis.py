"""
IS-IS Protocol Engine
Handles IS-IS (Intermediate System to Intermediate System) calculations and routing table generation
"""
import networkx as nx
from datetime import datetime


class ISISEngine:
    """IS-IS Protocol implementation"""
    
    def __init__(self):
        self.routing_tables = {}
        self.convergence_log = []
        self.levels = {'L1': [], 'L2': []}  # Track Level 1 and Level 2 routers
    
    def calculate_shortest_paths(self, graph, source_router):
        """
        Calculate shortest paths using IS-IS SPF algorithm
        IS-IS uses link metrics similar to OSPF
        
        Args:
            graph: NetworkX graph representing network topology
            source_router: Source router ID for IS-IS calculation
            
        Returns:
            Dictionary with routing table
        """
        try:
            lengths, paths = nx.single_source_dijkstra(graph, source_router, weight='weight')
            table = {}
            for dest in lengths:
                if dest == source_router: continue
                next_hop = paths[dest][1] if len(paths[dest]) > 1 else dest
                table[dest] = {'cost': lengths[dest], 'next_hop': next_hop}
            
            self.routing_tables[source_router] = table
            self.add_convergence_log(f"IS-IS SPF calculated for {source_router}: {len(table)} routes")
            
            return table
        except nx.NetworkXError as e:
            error_msg = f"Error calculating IS-IS routes from {source_router}: {str(e)}"
            self.add_convergence_log(error_msg)
            return {}
    
    def calculate_all_routing_tables(self, graph):
        """
        Calculate routing tables for all routers using IS-IS algorithm
        
        Args:
            graph: NetworkX graph representing network topology
            
        Returns:
            Dictionary mapping router IDs to their routing tables
        """
        self.routing_tables = {}
        
        for router in graph.nodes():
            self.calculate_shortest_paths(graph, router)
        
        self.add_convergence_log(f"IS-IS network converged. Total routers: {len(self.routing_tables)}")
        return self.routing_tables
    
    def get_routing_table(self, router_id):
        """Get routing table for a specific router"""
        return self.routing_tables.get(router_id, {})
    
    def add_convergence_log(self, message):
        """Add message to convergence log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.convergence_log.append(log_entry)
    
    def get_convergence_log(self):
        """Get convergence log entries"""
        return self.convergence_log
    
    def clear_convergence_log(self):
        """Clear convergence log"""
        self.convergence_log = []
    
    def estimate_convergence_time(self, graph, is_reconvergence=False):
        """
        Estimate IS-IS convergence time based on network topology.
        Calculates real-world values using LSP generation, SPF delays, and node counts.
        Typically faster than OSPF due to lack of DR wait timers and faster LSPs.
        """
        if graph.number_of_nodes() == 0:
            return 0.0
        
        try:
            if graph.number_of_nodes() == 1:
                diameter = 0
            elif nx.is_connected(graph):
                diameter = nx.diameter(graph)
            else:
                diameters = []
                for component in nx.connected_components(graph):
                    subgraph = graph.subgraph(component)
                    if subgraph.number_of_nodes() > 1:
                        diameters.append(nx.diameter(subgraph))
                diameter = max(diameters) if diameters else 0
        except:
            diameter = graph.number_of_nodes() - 1
            
        import math
        import random
        
        nodes = graph.number_of_nodes()
        edges = graph.number_of_edges()
        
        if not is_reconvergence:
            # IS-IS Initial Startup (No DR Wait timer like OSPF)
            base_startup = 5.0
            db_exchange = (edges * 0.03) + (nodes * 0.05)
            time_sec = base_startup + db_exchange
        else:
            # IS-IS Re-convergence (Tuned faster than OSPF typically)
            carrier_delay = 0.050         # 50ms Link fault detection
            lsp_gen_delay = 0.010         # 10ms LSP generation (fast)
            lsp_flood = diameter * 0.0005 # 0.5ms per hop
            spf_delay = 0.050             # 50ms initial SPF throttle timer
            spf_calc = (edges * math.log(nodes + 1 if nodes > 0 else 2)) * 0.00008
            fib_update = nodes * 0.0001
            
            time_sec = carrier_delay + lsp_gen_delay + lsp_flood + spf_delay + spf_calc + fib_update
            
        time_sec *= random.uniform(0.95, 1.05)
        return round(time_sec, 3)
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'lsp',
            'message_type': 'Link State PDUs (LSPs)',
            'description': 'IS-IS floods LSPs throughout network for link-state routing similar to OSPF',
            'title': 'IS-IS: LSP Flooding & SPF Calculation',
            'convergence_desc': 'Flood Link State PDUs to build topology and run SPF algorithm',
            'typical_time': '1-2 seconds'
        }
