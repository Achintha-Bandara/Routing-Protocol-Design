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
            lengths, paths = nx.single_source_dijkstra(graph, source_router, weight='weight')
            table = {}
            for dest in lengths:
                if dest == source_router: continue
                next_hop = paths[dest][1] if len(paths[dest]) > 1 else dest
                table[dest] = {'cost': lengths[dest], 'next_hop': next_hop}
            
            self.routing_tables[source_router] = table
            self.add_convergence_log(f"SPF calculated for {source_router}: {len(table)} routes")
            
            return table
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
    
    def estimate_convergence_time(self, graph, is_reconvergence=False):
        """
        Estimate OSPF convergence time based on network topology.
        Calculates real-world values using Carrier Delay, LSA generation/flooding,
        SPF computation (O(E log V)), and Wait timers.
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
            # Initial Startup (DR/BDR Election Wait Timer = 40s, Hello Exchange)
            base_startup = 40.0
            db_exchange = (edges * 0.05) + (nodes * 0.1)
            time_sec = base_startup + db_exchange
        else:
            # Re-convergence
            carrier_delay = 0.050         # 50ms Link fault detection
            lsa_gen_delay = 0.050         # 50ms LSA generation 
            lsa_flood = diameter * 0.001  # 1ms per hop
            spf_delay = 0.050             # 50ms initial SPF throttle timer
            spf_calc = (edges * math.log(nodes + 1 if nodes > 0 else 2)) * 0.0001
            fib_update = nodes * 0.0001
            
            time_sec = carrier_delay + lsa_gen_delay + lsa_flood + spf_delay + spf_calc + fib_update
            
        # Add 5% jitter to simulate real network variations
        time_sec *= random.uniform(0.95, 1.05)
        
        return round(time_sec, 3)
    
    def get_protocol_info(self):
        """Get protocol-specific animation and display information"""
        return {
            'animation_type': 'hello',
            'message_type': 'HELLO Packets',
            'description': 'OSPF uses HELLO packets to discover neighbors and establish adjacencies',
            'title': 'OSPF: HELLO Packet Exchange & SPF Calculation',
            'convergence_desc': 'Flood Link State Advertisements (LSAs) throughout network',
            'typical_time': '1-3 seconds'
        }
