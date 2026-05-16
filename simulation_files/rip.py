"""
RIP Protocol Engine
Handles RIP (Routing Information Protocol) calculations and routing table generation
"""
import networkx as nx
from datetime import datetime


class RIPEngine:
    """RIP Protocol implementation"""
    
    MAX_HOPS = 15  # RIP maximum hop count
    
    def __init__(self):
        self.routing_tables = {}
        self.convergence_log = []
    
    def calculate_shortest_paths(self, graph, source_router):
        """
        Calculate shortest paths using RIP distance-vector algorithm
        RIP uses hop count as metric with max 15 hops
        
        Args:
            graph: NetworkX graph representing network topology
            source_router: Source router ID for RIP calculation
            
        Returns:
            Dictionary with routing table (hop counts)
        """
        try:
            # In RIP, we count hops (each link = 1 hop)
            # Create unweighted version for hop counting
            unweighted_graph = nx.Graph()
            unweighted_graph.add_nodes_from(graph.nodes())
            unweighted_graph.add_edges_from(graph.edges())
            
            shortest_paths = nx.single_source_dijkstra_path_length(
                unweighted_graph, source_router
            )
            
            # Filter out unreachable destinations (hops > 15)
            filtered_paths = {dest: hops for dest, hops in shortest_paths.items() 
                             if hops <= self.MAX_HOPS}
            
            self.routing_tables[source_router] = filtered_paths
            self.add_convergence_log(f"RIP calculated for {source_router}: {len(filtered_paths)} routes")
            
            return filtered_paths
        except nx.NetworkXError as e:
            error_msg = f"Error calculating RIP routes from {source_router}: {str(e)}"
            self.add_convergence_log(error_msg)
            return {}
    
    def calculate_all_routing_tables(self, graph):
        """
        Calculate routing tables for all routers using RIP algorithm
        
        Args:
            graph: NetworkX graph representing network topology
            
        Returns:
            Dictionary mapping router IDs to their routing tables
        """
        self.routing_tables = {}
        
        for router in graph.nodes():
            self.calculate_shortest_paths(graph, router)
        
        self.add_convergence_log(f"RIP network converged. Total routers: {len(self.routing_tables)}")
        return self.routing_tables
    
    def get_routing_table(self, router_id):
        """Get routing table for a specific router"""
        return self.routing_tables.get(router_id, {})
    
    def add_convergence_log(self, message):
        """Add message to convergence log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.convergence_log.append(log_entry)
    
    def estimate_convergence_time(self, graph):
        """
        Estimate RIP convergence time based on network topology.
        RIP convergence factors:
        - Update interval: 30 seconds (industry standard)
        - Propagation: One hop per update cycle
        - Settling: 3-5 update cycles for full convergence
        Real-world: 90-180 seconds for typical networks
        """
        if graph.number_of_nodes() == 0:
            return 0.0
        
        try:
            if graph.number_of_nodes() == 1:
                diameter = 0
            elif graph.is_connected():
                diameter = len(list(graph.nodes())) - 1
            else:
                diameters = []
                for component in nx.connected_components(graph):
                    subgraph = graph.subgraph(component)
                    if subgraph.number_of_nodes() > 1:
                        diameters.append(len(list(subgraph.nodes())) - 1)
                diameter = max(diameters) if diameters else 0
        except:
            diameter = graph.number_of_nodes() - 1
        
        convergence_time = 30 + (diameter * 30) + 30
        return round(min(convergence_time, 300.0), 3)
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'distance_vector',
            'message_type': 'Periodic RESPONSE/UPDATE',
            'description': 'RIP uses distance-vector algorithm with periodic updates (hop count metric, max 15 hops)',
            'title': 'RIP: Distance-Vector Route Distribution',
            'convergence_desc': 'Exchange distance-vector information periodically between neighbors',
            'typical_time': '90-180 seconds'
        }
    
    def get_convergence_log(self):
        """Get convergence log entries"""
        return self.convergence_log
    
    def clear_convergence_log(self):
        """Clear convergence log"""
        self.convergence_log = []
