from simulator import RouterNode

class BGPNode(RouterNode):
    def __init__(self, node_id):
        super().__init__(node_id)
        self.my_as = f"AS{hash(node_id)%1000 + 100}"
        self.routing_table[self.id] = {'as_path': [self.my_as], 'next_hop': self.id, 'metric': 0}
        self.neighbors_status = {}
        
    def start(self):
        import random
        jitter = random.uniform(0, 5.0)
        self.simulator.schedule(jitter, self._send_keepalive, f"BGP KA {self.id}")
        self.simulator.schedule(1.0, self._check_timers, f"BGP Timers {self.id}")
        self.simulator.schedule(2.0, self._process_mrai, f"BGP MRAI {self.id}")
        
    def _send_keepalive(self):
        payload = {'type': 'KEEPALIVE', 'router_id': self.id}
        for neighbor in self.get_neighbors():
            self.simulator.send_packet(self.id, neighbor, payload, color="#9b59b6")
        self.simulator.schedule(60.0, self._send_keepalive, f"BGP KA {self.id}")
        
    def _check_timers(self):
        current_time = self.simulator.sim_time
        changed = False
        to_remove = []
        for neighbor, last_ka in self.neighbors_status.items():
            if current_time - last_ka > 180.0:
                to_remove.append(neighbor)
                changed = True
                
        for neighbor in to_remove:
            del self.neighbors_status[neighbor]
            routes_to_delete = [d for d, info in self.routing_table.items() if info['next_hop'] == neighbor]
            for d in routes_to_delete:
                del self.routing_table[d]
                
        if changed:
            self.last_update_time = self.simulator.sim_time
            
        self.simulator.schedule(1.0, self._check_timers, f"BGP Timers {self.id}")
        
    def link_up(self, neighbor):
        # We don't have _send_update, but we process MRAI periodically. We can trigger an update by just processing MRAI immediately.
        self._process_mrai()
        
    def _process_mrai(self):
        payload = {'type': 'UPDATE', 'routes': {}}
        for dest, info in self.routing_table.items():
            payload['routes'][dest] = info
            
        for neighbor in self.get_neighbors():
            neighbor_payload = {'type': 'UPDATE', 'routes': {}}
            for dest, info in payload['routes'].items():
                if info['next_hop'] != neighbor:
                    neighbor_payload['routes'][dest] = info
            self.simulator.send_packet(self.id, neighbor, neighbor_payload, color="#3498db")
            
        self.simulator.schedule(5.0, self._process_mrai, f"BGP MRAI {self.id}")
        
    def receive_packet(self, src, payload):
        if payload['type'] == 'KEEPALIVE':
            self.neighbors_status[src] = self.simulator.sim_time
            return
            
        if payload['type'] == 'UPDATE':
            self.neighbors_status[src] = self.simulator.sim_time
            changed = False
            
            for dest, info in payload['routes'].items():
                if dest == self.id: continue
                if self.my_as in info['as_path']:
                    continue
                    
                new_as_path = [self.my_as] + info['as_path']
                new_metric = len(new_as_path)
                
                if dest not in self.routing_table:
                    self.routing_table[dest] = {'as_path': new_as_path, 'next_hop': src, 'metric': new_metric}
                    changed = True
                else:
                    current_info = self.routing_table[dest]
                    if current_info['next_hop'] == src:
                        if current_info['as_path'] != new_as_path:
                            self.routing_table[dest] = {'as_path': new_as_path, 'next_hop': src, 'metric': new_metric}
                            changed = True
                    elif new_metric < current_info['metric']:
                        self.routing_table[dest] = {'as_path': new_as_path, 'next_hop': src, 'metric': new_metric}
                        changed = True
                        
            if changed:
                self.last_update_time = self.simulator.sim_time

class BGPEngine:
    def get_protocol_info(self):
        return {
            'animation_type': 'update',
            'message_type': 'BGP UPDATE/KEEPALIVE',
            'description': 'BGP Path-Vector with MRAI and Keepalive',
            'title': 'BGP: Real-time Path-Vector',
            'convergence_desc': 'Converging using UPDATE messages',
            'typical_time': 'Real-time simulated'
        }
    def create_node(self, node_id):
        return BGPNode(node_id)
