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
            
            lengths, paths = nx.single_source_dijkstra(unweighted_graph, source_router)
            
            table = {}
            for dest, hops in lengths.items():
                if hops <= self.MAX_HOPS and dest != source_router:
                    next_hop = paths[dest][1] if len(paths[dest]) > 1 else dest
                    table[dest] = {'cost': hops, 'next_hop': next_hop}
            
            self.routing_tables[source_router] = table
            self.add_convergence_log(f"RIP calculated for {source_router}: {len(table)} routes")
            
            return table
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
    
    def estimate_convergence_time(self, graph, is_reconvergence=False):
        """
        Estimate RIP convergence time based on network topology.
        Calculates real-world values using 30s periodic timers, invalid timers (180s),
        and count-to-infinity characteristics.
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
        
        if not is_reconvergence:
            # RIP Initial Startup
            avg_wait = 15.0 # Average wait for next 30s periodic update
            propagation = diameter * 2.0
            time_sec = avg_wait + propagation
        else:
            # RIP Re-convergence (Slow, Invalid Timer + Triggered Updates)
            invalid_timer = 180.0
            propagation = diameter * 1.5
            time_sec = invalid_timer + propagation
            
        time_sec *= random.uniform(0.95, 1.05)
        return round(time_sec, 3)
    
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
