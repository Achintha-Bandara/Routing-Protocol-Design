"""
OSPF Protocol Engine
Handles OSPF protocol calculations and routing table generation
"""
import networkx as nx
from datetime import datetime


class OSPFEngine:
    """OSPF Protocol implementation"""
    
    def __init__(self):
        self.routing_tables = {}
        self.convergence_log = []
    
    def calculate_shortest_paths(self, graph, source_router):
        """
        Calculate shortest paths using Dijkstra's algorithm (SPF - Shortest Path First)
        This is the core of OSPF routing
        
        Args:
            graph: NetworkX graph representing network topology
            source_router: Source router ID for SPF calculation
            
        Returns:
            Dictionary with routing table
        """
        try:
            shortest_paths = nx.single_source_dijkstra_path_length(
                graph, source_router, weight='weight'
            )
            
            self.routing_tables[source_router] = shortest_paths
            self.add_convergence_log(f"SPF calculated for {source_router}: {len(shortest_paths)} routes")
            
            return shortest_paths
        except nx.NetworkXError as e:
            error_msg = f"Error calculating routes from {source_router}: {str(e)}"
            self.add_convergence_log(error_msg)
            return {}
    
    def calculate_all_routing_tables(self, graph):
        """
        Calculate routing tables for all routers in network
        
        Args:
            graph: NetworkX graph representing network topology
            
        Returns:
            Dictionary mapping router IDs to their routing tables
        """
        self.routing_tables = {}
        
        for router in graph.nodes():
            self.calculate_shortest_paths(graph, router)
        
        self.add_convergence_log(f"Network converged. Total routers: {len(self.routing_tables)}")
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
            'animation_type': 'hello',
            'message_type': 'HELLO Packets',
            'description': 'OSPF uses HELLO packets to discover neighbors and establish adjacencies',
            'title': 'OSPF: HELLO Packet Exchange & SPF Calculation',
            'convergence_desc': 'Flood Link State Advertisements (LSAs) throughout network'
        }
