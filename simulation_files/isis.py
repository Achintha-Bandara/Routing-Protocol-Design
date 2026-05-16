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
            shortest_paths = nx.single_source_dijkstra_path_length(
                graph, source_router, weight='weight'
            )
            
            self.routing_tables[source_router] = shortest_paths
            self.add_convergence_log(f"IS-IS SPF calculated for {source_router}: {len(shortest_paths)} routes")
            
            return shortest_paths
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
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'lsp',
            'message_type': 'Link State PDUs (LSPs)',
            'description': 'IS-IS floods LSPs throughout network for link-state routing similar to OSPF',
            'title': 'IS-IS: LSP Flooding & SPF Calculation',
            'convergence_desc': 'Flood Link State PDUs to build topology and run SPF algorithm'
        }
