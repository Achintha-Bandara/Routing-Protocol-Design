from simulator import RouterNode

class RIPNode(RouterNode):
    MAX_HOPS = 15
    
    def __init__(self, node_id):
        super().__init__(node_id)
        # destination -> {'cost': int, 'next_hop': str, 'timer': float}
        self.routing_table[self.id] = {'cost': 0, 'next_hop': self.id, 'timer': float('inf')}
        
    def start(self):
        import random
        jitter = random.uniform(0, 5.0)
        self.simulator.schedule(jitter, self._send_periodic_update, f"RIP Init {self.id}")
        self.simulator.schedule(1.0, self._check_timers, f"RIP Timer {self.id}")
        
    def _send_periodic_update(self):
        self._broadcast_table()
        import random
        self.simulator.schedule(30.0 + random.uniform(-2, 2), self._send_periodic_update, f"RIP Update {self.id}")
        
    def _broadcast_table(self):
        neighbors = self.get_neighbors()
        for neighbor in neighbors:
            payload = {}
            for dest, info in self.routing_table.items():
                if info['next_hop'] == neighbor and dest != self.id:
                    # Split Horizon with Poison Reverse
                    payload[dest] = 16
                else:
                    payload[dest] = info['cost']
            
            self.simulator.send_packet(self.id, neighbor, payload, color="#e74c3c")
            
    def _check_timers(self):
        changed = False
        current_time = self.simulator.sim_time
        to_delete = []
        for dest, info in self.routing_table.items():
            if dest == self.id: continue
            
            time_since_update = current_time - info['timer']
            
            # Invalid Timer (180s)
            if time_since_update > 180.0 and info['cost'] < 16:
                info['cost'] = 16
                changed = True
                
            # Flush Timer (240s)
            if time_since_update > 240.0:
                to_delete.append(dest)
                changed = True
                
        for dest in to_delete:
            del self.routing_table[dest]
            
        if changed:
            self.last_update_time = current_time
            self._broadcast_table() # Triggered update
            
    def link_up(self, neighbor):
        self._broadcast_table()
            
        self.simulator.schedule(1.0, self._check_timers, f"RIP Timer {self.id}")
        
    def receive_packet(self, src, payload):
        changed = False
        current_time = self.simulator.sim_time
        
        for dest, cost in payload.items():
            new_cost = min(cost + 1, 16)
            
            if dest not in self.routing_table:
                if new_cost < 16:
                    self.routing_table[dest] = {'cost': new_cost, 'next_hop': src, 'timer': current_time}
                    changed = True
            else:
                current_info = self.routing_table[dest]
                if current_info['next_hop'] == src:
                    current_info['timer'] = current_time
                    if current_info['cost'] != new_cost:
                        current_info['cost'] = new_cost
                        changed = True
                elif new_cost < current_info['cost']:
                    self.routing_table[dest] = {'cost': new_cost, 'next_hop': src, 'timer': current_time}
                    changed = True
                    
        if changed:
            self.last_update_time = current_time
            self._broadcast_table()

class RIPEngine:
    def get_protocol_info(self):
        return {
            'animation_type': 'distance_vector',
            'message_type': 'RIP Updates',
            'description': 'RIP distance-vector algorithm with 30s updates',
            'title': 'RIP: Real-time Distance-Vector',
            'convergence_desc': 'Converging using periodic updates and timers',
            'typical_time': 'Real-time simulated'
        }
    def create_node(self, node_id):
        return RIPNode(node_id)
