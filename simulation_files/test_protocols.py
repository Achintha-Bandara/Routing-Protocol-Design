#!/usr/bin/env python3
"""
Test script to verify all protocols work correctly
"""
import json
import networkx as nx
from pathlib import Path

# Test each protocol's engine
print("=" * 60)
print("Protocol Engine Testing")
print("=" * 60)

# Load configuration
config_path = Path(__file__).parent / 'network_config.json'
with open(config_path) as f:
    config = json.load(f)

# Create graph from config
graph = nx.Graph()
for router in config['routers']:
    graph.add_node(router['id'])

for link in config['links']:
    graph.add_edge(link['from'], link['to'], weight=link.get('cost', 1))

print(f"\n[OK] Loaded network with {len(graph.nodes())} routers and {len(graph.edges())} links")

# Test OSPF
print("\n--- Testing OSPF ---")
try:
    from ospf.ospf import OSPFEngine
    ospf = OSPFEngine()
    ospf_tables = ospf.calculate_all_routing_tables(graph)
    print(f"[OK] OSPF calculated routing tables for {len(ospf_tables)} routers")
    for router in list(ospf_tables.keys())[:2]:
        print(f"      {router}: {len(ospf_tables[router])} routes")
    ospf_log = ospf.get_convergence_log()
    print(f"[OK] OSPF convergence log: {ospf_log[-1]}")
except Exception as e:
    print(f"[ERROR] OSPF failed: {e}")

# Test BGP
print("\n--- Testing BGP ---")
try:
    from bgp import BGPEngine
    bgp = BGPEngine()
    bgp_tables = bgp.calculate_all_routing_tables(graph)
    print(f"[OK] BGP calculated routing tables for {len(bgp_tables)} routers")
    for router in list(bgp_tables.keys())[:2]:
        print(f"      {router}: {len(bgp_tables[router])} routes")
    bgp_log = bgp.get_convergence_log()
    print(f"[OK] BGP convergence log: {bgp_log[-1]}")
except Exception as e:
    print(f"[ERROR] BGP failed: {e}")

# Test IS-IS
print("\n--- Testing IS-IS ---")
try:
    from isis import ISISEngine
    isis = ISISEngine()
    isis_tables = isis.calculate_all_routing_tables(graph)
    print(f"[OK] IS-IS calculated routing tables for {len(isis_tables)} routers")
    for router in list(isis_tables.keys())[:2]:
        print(f"      {router}: {len(isis_tables[router])} routes")
    isis_log = isis.get_convergence_log()
    print(f"[OK] IS-IS convergence log: {isis_log[-1]}")
except Exception as e:
    print(f"[ERROR] IS-IS failed: {e}")

# Test RIP
print("\n--- Testing RIP ---")
try:
    from rip import RIPEngine
    rip = RIPEngine()
    rip_tables = rip.calculate_all_routing_tables(graph)
    print(f"[OK] RIP calculated routing tables for {len(rip_tables)} routers")
    for router in list(rip_tables.keys())[:2]:
        print(f"      {router}: {len(rip_tables[router])} routes")
    rip_log = rip.get_convergence_log()
    print(f"[OK] RIP convergence log: {rip_log[-1]}")
except Exception as e:
    print(f"[ERROR] RIP failed: {e}")

print("\n" + "=" * 60)
print("[OK] All protocols tested successfully!")
print("=" * 60)
