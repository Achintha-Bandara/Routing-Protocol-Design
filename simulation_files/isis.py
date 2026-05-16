from simulator import RouterNode
import networkx as nx

class ISISNode(RouterNode):
    def __init__(self, node_id):
        super().__init__(node_id)
        self.lsdb = {}
        self.seq_num = 0
        self.neighbors_status = {}
        self.spf_scheduled = False
        
    def start(self):
        import random
        jitter = random.uniform(0, 1.0)
        self.simulator.schedule(jitter, self._send_hello, f"ISIS Hello {self.id}")
        self.simulator.schedule(1.0, self._check_hold_timers, f"ISIS Hold Timer {self.id}")
        self._generate_lsp()
        
    def _send_hello(self):
        payload = {'type': 'HELLO', 'router_id': self.id}
        for neighbor in self.get_neighbors():
            self.simulator.send_packet(self.id, neighbor, payload, color="#f1c40f")
        self.simulator.schedule(10.0, self._send_hello, f"ISIS Hello {self.id}")
        
    def _check_hold_timers(self):
        current_time = self.simulator.sim_time
        changed = False
        to_remove = []
        for neighbor, last_hello in self.neighbors_status.items():
            if current_time - last_hello > 30.0:
                to_remove.append(neighbor)
                changed = True
                
        for neighbor in to_remove:
            del self.neighbors_status[neighbor]
            
        if changed:
            self._generate_lsp()
            
        self.simulator.schedule(1.0, self._check_hold_timers, f"ISIS Hold Timer {self.id}")
        
    def _generate_lsp(self):
        self.seq_num += 1
        links = {}
        for neighbor in self.get_neighbors():
            if (self.id, neighbor) in self.simulator.links:
                cost = self.simulator.links[(self.id, neighbor)]['cost']
                links[neighbor] = cost
                
        lsp = {'router_id': self.id, 'seq': self.seq_num, 'links': links}
        self.lsdb[self.id] = {'seq': self.seq_num, 'links': links, 'timer': self.simulator.sim_time}
        
        self._flood_lsp(lsp, exclude_neighbor=None)
        self._schedule_spf()
        
    def _flood_lsp(self, lsp, exclude_neighbor):
        payload = {'type': 'LSP', 'lsp': lsp}
        for neighbor in self.get_neighbors():
            if neighbor != exclude_neighbor:
                self.simulator.send_packet(self.id, neighbor, payload, color="#d35400")
                
    def receive_packet(self, src, payload):
        if payload['type'] == 'HELLO':
            if src not in self.neighbors_status:
                self.neighbors_status[src] = self.simulator.sim_time
                self._generate_lsp()
            else:
                self.neighbors_status[src] = self.simulator.sim_time
        elif payload['type'] == 'LSP':
            lsp = payload['lsp']
            origin = lsp['router_id']
            seq = lsp['seq']
            
            current_lsp = self.lsdb.get(origin)
            if not current_lsp or seq > current_lsp['seq']:
                self.lsdb[origin] = {'seq': seq, 'links': lsp['links'], 'timer': self.simulator.sim_time}
                self._flood_lsp(lsp, exclude_neighbor=src)
                self._schedule_spf()
                
    def _schedule_spf(self):
        if not self.spf_scheduled:
            self.spf_scheduled = True
            self.simulator.schedule(0.05, self._run_spf, f"SPF {self.id}")
            
    def _run_spf(self):
        self.spf_scheduled = False
        self.last_update_time = self.simulator.sim_time
        
        graph = nx.Graph()
        for router_id, lsp_info in self.lsdb.items():
            for neighbor, cost in lsp_info['links'].items():
                graph.add_edge(router_id, neighbor, weight=cost)
                
        try:
            lengths, paths = nx.single_source_dijkstra(graph, self.id, weight='weight')
            table = {}
            for dest in lengths:
                if dest == self.id: continue
                next_hop = paths[dest][1] if len(paths[dest]) > 1 else dest
                table[dest] = {'cost': lengths[dest], 'next_hop': next_hop}
            self.routing_table = table
        except Exception:
            pass

    def link_up(self, neighbor):
        self._send_hello()

class ISISEngine:
    def get_protocol_info(self):
        return {
            'animation_type': 'lsp',
            'message_type': 'IS-IS LSP/Hello',
            'description': 'IS-IS Link-State with 10s Hello and fast SPF',
            'title': 'IS-IS: Real-time Link-State',
            'convergence_desc': 'Converging using LSP flooding',
            'typical_time': 'Real-time simulated'
        }
    def create_node(self, node_id):
        return ISISNode(node_id)
