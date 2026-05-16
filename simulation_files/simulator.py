import heapq
import re
import networkx as nx

class BandwidthParser:
    @staticmethod
    def parse(bw_str):
        if not bw_str:
            return 1e9  # Default 1Gbps
        match = re.match(r"(\d+)(Mbps|Gbps|Kbps)", bw_str, re.IGNORECASE)
        if not match:
            return 1e9
        val = int(match.group(1))
        unit = match.group(2).lower()
        if unit == "gbps":
            return val * 1e9
        elif unit == "mbps":
            return val * 1e6
        elif unit == "kbps":
            return val * 1e3
        return val

class Event:
    def __init__(self, time, callback, desc=""):
        self.time = time
        self.callback = callback
        self.desc = desc
    
    def __lt__(self, other):
        return self.time < other.time

class Simulator:
    def __init__(self):
        self.sim_time = 0.0
        self.events = []
        self.speed_multiplier = 1.0  # e.g., 10x means 1 real sec = 10 sim sec
        self.nodes = {}
        self.links = {}  # (u, v) -> {'bandwidth': bps, 'delay': sec, 'cost': int}
        self.packets_in_transit = []
        self.topology_changed_at = 0.0
        self.convergence_callback = None
        self.is_converging = False
        self.last_convergence_check = 0.0
        
    def schedule(self, delay, callback, desc=""):
        heapq.heappush(self.events, Event(self.sim_time + delay, callback, desc))
        
    def reset(self):
        self.sim_time = 0.0
        self.events = []
        self.packets_in_transit = []
        self.is_converging = False
        
    def add_node(self, node_id, node_obj):
        self.nodes[node_id] = node_obj
        node_obj.simulator = self
        
    def add_link(self, u, v, cost, bandwidth_str):
        bps = BandwidthParser.parse(bandwidth_str)
        # Propagation delay + base processing delay.
        # Fixed 0.5s sim-time delay to make packets visible during animation
        # The user wants exact bandwidth logic, so we could factor bps in, 
        # but UI visibility demands a minimum visual delay.
        tx_delay = (1500 * 8) / bps
        delay = 0.5 + tx_delay
        
        self.links[(u, v)] = {'cost': cost, 'bandwidth': bps, 'delay': delay}
        self.links[(v, u)] = {'cost': cost, 'bandwidth': bps, 'delay': delay}
        
        if u in self.nodes: self.nodes[u].link_up(v)
        if v in self.nodes: self.nodes[v].link_up(u)
        
    def remove_link(self, u, v):
        if (u, v) in self.links:
            del self.links[(u, v)]
        if (v, u) in self.links:
            del self.links[(v, u)]
            
        if u in self.nodes: self.nodes[u].link_down(v)
        if v in self.nodes: self.nodes[v].link_down(u)
            
        self.trigger_topology_change()
            
    def trigger_topology_change(self):
        self.topology_changed_at = self.sim_time
        self.is_converging = True
        
    def check_convergence(self):
        if not self.is_converging:
            return
            
        if self.sim_time - self.topology_changed_at < 2.0:
            return
            
        # If all nodes say they haven't updated their tables recently, we converged
        for node in self.nodes.values():
            if self.sim_time - node.last_update_time < 2.0:  # Need 2s of quiet time
                return
                
            # Check for routes pointing to dead links (meaning the node is waiting for a timeout)
            for dest, info in node.routing_table.items():
                cost = info.get('cost', info.get('metric', 0))
                # Ignore explicitly unreachable routes (RIP cost 16, or generic 9999)
                if type(node).__name__ == 'RIPNode' and cost >= 16:
                    continue
                if cost >= 9999:
                    continue
                    
                next_hop = info.get('next_hop', dest)
                if next_hop != node.id and next_hop is not None:
                    if (node.id, next_hop) not in self.links:
                        # Node relies on a dead link -> not converged!
                        return
                
        # Converged!
        self.is_converging = False
        conv_time = self.sim_time - self.topology_changed_at
        if self.convergence_callback:
            self.convergence_callback(conv_time)
            
    def send_packet(self, src, dst, payload, color="#3498db"):
        if (src, dst) not in self.links:
            return  # Link is down
            
        delay = self.links[(src, dst)]['delay']
        arrival_time = self.sim_time + delay
        
        packet = {
            'src': src,
            'dst': dst,
            'start_time': self.sim_time,
            'arrival_time': arrival_time,
            'payload': payload,
            'color': color
        }
        self.packets_in_transit.append(packet)
        
        def deliver():
            if (src, dst) in self.links and dst in self.nodes:
                self.nodes[dst].receive_packet(src, payload)
        self.schedule(delay, deliver, f"Pkt {src}->{dst}")
        
    def tick(self, delta_real_seconds):
        delta_sim = delta_real_seconds * self.speed_multiplier
        target_sim_time = self.sim_time + delta_sim
        
        # Execute events up to target_sim_time
        while self.events and self.events[0].time <= target_sim_time:
            event = heapq.heappop(self.events)
            self.sim_time = event.time
            event.callback()
            
        self.sim_time = target_sim_time
        
        # Cleanup arrived packets
        self.packets_in_transit = [p for p in self.packets_in_transit if p['arrival_time'] > self.sim_time]
        
        # Periodically check convergence
        if self.sim_time - self.last_convergence_check >= 0.5:
            self.last_convergence_check = self.sim_time
            self.check_convergence()

class RouterNode:
    def __init__(self, node_id):
        self.id = node_id
        self.simulator = None
        self.last_update_time = 0.0
        self.routing_table = {}
        
    def start(self):
        pass
        
    def receive_packet(self, src, payload):
        pass
        
    def link_up(self, neighbor):
        pass
        
    def link_down(self, neighbor):
        pass
        
    def get_neighbors(self):
        neighbors = []
        for (u, v) in self.simulator.links.keys():
            if u == self.id:
                neighbors.append(v)
        return neighbors
