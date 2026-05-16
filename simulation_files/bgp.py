"""
BGP Protocol Engine
Handles BGP (Border Gateway Protocol) calculations and routing table generation
"""
import networkx as nx
from datetime import datetime


class BGPEngine:
    """BGP Protocol implementation"""
    
    def __init__(self):
        self.routing_tables = {}
        self.convergence_log = []
        self.as_numbers = {}  # Track AS numbers
    
    def calculate_shortest_paths(self, graph, source_router):
        """
        Calculate shortest paths using BGP path selection algorithm
        BGP uses AS Path length as primary metric
        
        Args:
            graph: NetworkX graph representing network topology
            source_router: Source router ID for BGP calculation
            
        Returns:
            Dictionary with routing table
        """
        try:
            lengths, paths = nx.single_source_dijkstra(graph, source_router, weight='weight')
            table = {}
            for dest in lengths:
                if dest == source_router: continue
                next_hop = paths[dest][1] if len(paths[dest]) > 1 else dest
                as_path = " ".join([f"AS{hash(node)%1000 + 100}" for node in paths[dest][1:]])
                table[dest] = {'cost': lengths[dest], 'next_hop': next_hop, 'as_path': as_path}
            
            self.routing_tables[source_router] = table
            self.add_convergence_log(f"BGP calculated for {source_router}: {len(table)} routes")
            
            return table
        except nx.NetworkXError as e:
            error_msg = f"Error calculating BGP routes from {source_router}: {str(e)}"
            self.add_convergence_log(error_msg)
            return {}
    
    def calculate_all_routing_tables(self, graph):
        """
        Calculate routing tables for all routers using BGP algorithm
        
        Args:
            graph: NetworkX graph representing network topology
            
        Returns:
            Dictionary mapping router IDs to their routing tables
        """
        self.routing_tables = {}
        
        for router in graph.nodes():
            self.calculate_shortest_paths(graph, router)
        
        self.add_convergence_log(f"BGP network converged. Total routers: {len(self.routing_tables)}")
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
        Estimate BGP convergence time based on network topology.
        Calculates real-world values using TCP handshake limits, MRAI timers, 
        and Path Exploration effects based on network diameter.
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
            
        import random
        
        nodes = graph.number_of_nodes()
        
        if not is_reconvergence:
            # BGP Initial Startup (TCP Handshake, Open, Table Transfer)
            base_startup = 2.0
            table_transfer = nodes * 0.05
            time_sec = base_startup + table_transfer
        else:
            # BGP Re-convergence (MRAI timers and Path Exploration)
            detection = 0.050
            best_path_calc = nodes * 0.001
            mrai_timer = 5.0  # Average mix of iBGP (5s) and eBGP (30s) timers
            path_exploration_delay = diameter * mrai_timer
            
            time_sec = detection + best_path_calc + path_exploration_delay
            
        time_sec *= random.uniform(0.95, 1.05)
        return round(time_sec, 3)
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'update',
            'message_type': 'UPDATE Messages',
            'description': 'BGP exchanges UPDATE messages to advertise and withdraw routes based on AS-PATH',
            'title': 'BGP: UPDATE Message Exchange & Path Selection',
            'convergence_desc': 'Propagate routes via UPDATE messages between autonomous systems',
            'typical_time': '20-60+ seconds'
        }
