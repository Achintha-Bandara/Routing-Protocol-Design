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
            shortest_paths = nx.single_source_dijkstra_path_length(
                graph, source_router, weight='weight'
            )
            
            self.routing_tables[source_router] = shortest_paths
            self.add_convergence_log(f"BGP calculated for {source_router}: {len(shortest_paths)} routes")
            
            return shortest_paths
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
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'update',
            'message_type': 'UPDATE Messages',
            'description': 'BGP exchanges UPDATE messages to advertise and withdraw routes based on AS-PATH',
            'title': 'BGP: UPDATE Message Exchange & Path Selection',
            'convergence_desc': 'Propagate routes via UPDATE messages between autonomous systems'
        }
