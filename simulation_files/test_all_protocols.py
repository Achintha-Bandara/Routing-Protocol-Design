"""
Quick test script to verify all protocols load and work correctly
"""
import networkx as nx
from ospf import OSPFEngine
from bgp import BGPEngine
from rip import RIPEngine
from isis import ISISEngine

# Create a simple test graph
def create_test_graph():
    graph = nx.Graph()
    graph.add_edge('R1', 'R2', weight=1)
    graph.add_edge('R2', 'R3', weight=1)
    graph.add_edge('R3', 'R4', weight=2)
    graph.add_edge('R1', 'R4', weight=5)
    return graph

# Test each protocol
protocols = {
    'OSPF': OSPFEngine(),
    'BGP': BGPEngine(),
    'RIP': RIPEngine(),
    'IS-IS': ISISEngine()
}

graph = create_test_graph()

print("=" * 60)
print("Testing All Protocols")
print("=" * 60)

for protocol_name, engine in protocols.items():
    print(f"\n[{protocol_name}] Testing...")
    
    # Get protocol info
    info = engine.get_protocol_info()
    print(f"  Message Type: {info['message_type']}")
    print(f"  Animation Type: {info['animation_type']}")
    print(f"  Description: {info['description']}")
    
    # Calculate routing tables
    routing_tables = engine.calculate_all_routing_tables(graph)
    print(f"  Routers: {len(routing_tables)}")
    
    # Show sample routing table for R1
    if 'R1' in routing_tables:
        rt = routing_tables['R1']
        print(f"  R1 Routes: {dict(sorted(rt.items()))}")
    
    # Get convergence log
    log = engine.get_convergence_log()
    print(f"  Convergence Log: {log[-1]}")

print("\n" + "=" * 60)
print("All Protocols Tested Successfully!")
print("=" * 60)
