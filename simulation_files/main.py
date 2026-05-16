import tkinter as tk
from tkinter import messagebox
import json
import os
import sys
import threading
import time
from pathlib import Path
import networkx as nx

from simulator import Simulator

# ====== PROTOCOL SELECTION ======
PROTOCOL_NAME = 'rip'

if PROTOCOL_NAME == 'ospf':
    from ospf import OSPFEngine
    ProtocolEngine = OSPFEngine
elif PROTOCOL_NAME == 'bgp':
    from bgp import BGPEngine
    ProtocolEngine = BGPEngine
elif PROTOCOL_NAME == 'isis':
    from isis import ISISEngine
    ProtocolEngine = ISISEngine
elif PROTOCOL_NAME == 'rip':
    from rip import RIPEngine
    ProtocolEngine = RIPEngine
else:
    raise ValueError(f"Unknown protocol: {PROTOCOL_NAME}")

from ui import OSPFSimulatorUI

class ConfigLoader:
    @staticmethod
    def load_config(config_path):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        ConfigLoader.validate_config(config)
        return config
    
    @staticmethod
    def validate_config(config):
        required_fields = ['network', 'routers', 'links']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field in config: {field}")
        routers = config['routers']
        if not isinstance(routers, list) or len(routers) < 2:
            raise ValueError("Must have at least 2 routers")
        for router in routers:
            if 'id' not in router or 'name' not in router:
                raise ValueError("Each router must have 'id' and 'name'")

class JSONFileWatcher:
    def __init__(self, config_path, callback):
        self.config_path = config_path
        self.callback = callback
        self.last_modified = os.path.getmtime(config_path) if os.path.exists(config_path) else None
        self.running = True
        self.watch_thread = threading.Thread(target=self._watch_file, daemon=True)
        self.watch_thread.start()
    
    def _watch_file(self):
        while self.running:
            try:
                if os.path.exists(self.config_path):
                    current_modified = os.path.getmtime(self.config_path)
                    if self.last_modified is not None and current_modified > self.last_modified:
                        self.last_modified = current_modified
                        time.sleep(0.5)
                        self.callback()
                    elif self.last_modified is None:
                        self.last_modified = current_modified
            except Exception as e:
                pass
            time.sleep(1)
    
    def stop(self):
        self.running = False

class ProtocolSimulator:
    def __init__(self, root, config_path):
        self.root = root
        self.config_path = config_path
        self.config = None
        self.graph = nx.Graph()
        self.protocol_engine = ProtocolEngine()
        self.simulator = Simulator()
        self.simulator.convergence_callback = self.on_converged
        self.ui = None
        self.file_watcher = None
        self.updating = False
        self.failed_links = set()
        
        self.load_configuration()
        self.setup_ui()
        self.start_file_watcher()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start simulation loop
        self.last_real_time = time.time()
        self._tick()
        
    def load_configuration(self):
        try:
            self.config = ConfigLoader.load_config(self.config_path)
            return True
        except Exception as e:
            return False
            
    def reload_network(self):
        if self.updating: return
        self.updating = True
        try:
            if not self.load_configuration():
                self.updating = False
                return
            self.root.after(0, self._perform_ui_update)
        except Exception as e:
            self.updating = False
            
    def _perform_ui_update(self):
        try:
            self.update_ui()
            if self.ui:
                self.ui.update_status(f"[OK] Configuration reloaded", "#27ae60")
        except Exception as e:
            pass
        finally:
            self.updating = False
            
    def setup_ui(self):
        network_info = self.config.get('network', {}) if self.config else None
        self.ui = OSPFSimulatorUI(self.root, network_info, protocol_name=PROTOCOL_NAME.upper())
        if self.config:
            self.update_ui()
        
        self.ui.fail_link_btn.config(command=self.fail_link)
        self.ui.recover_link_btn.config(command=self.recover_link)
        self.ui.skip_btn.config(command=self.skip_to_converged)
        
    def update_ui(self):
        if not self.config: return
        self.simulator.reset()
        self.graph.clear()
        
        routers = self.config.get('routers', [])
        for r in routers:
            node = self.protocol_engine.create_node(r['id'])
            self.simulator.add_node(r['id'], node)
            self.graph.add_node(r['id'], name=r.get('name', ''))
            
        links = self.config.get('links', [])
        for l in links:
            self.simulator.add_link(l['from'], l['to'], l.get('cost', 1), l.get('bandwidth', '1Gbps'))
            self.graph.add_edge(l['from'], l['to'], weight=l.get('cost', 1))
            
        self.ui.update_topology_info(self.config.get('network', {}), routers)
        self.ui.draw_topology(self.graph)
        self.ui.update_router_list(routers)
        
        link_names = [f"{link['from']}-{link['to']}" for link in links]
        self.ui.link_combo['values'] = link_names
        if link_names: self.ui.link_combo.current(0)
        
        self.failed_links = set()
        self.ui.fail_link_btn.config(state="normal")
        self.ui.recover_link_btn.config(state="disabled")
        
        for node in self.simulator.nodes.values():
            node.start()
            
        self.simulator.trigger_topology_change()
            
    def on_converged(self, conv_time):
        self.ui.update_estimated_convergence_time(conv_time)
        self.ui.update_status(f"Converged in {conv_time:.3f}s", "#27ae60")
        
    def _tick(self):
        if not self.updating:
            current_time = time.time()
            delta_time = current_time - self.last_real_time
            self.last_real_time = current_time
            
            # Limit delta_time to avoid massive jumps if thread stalled
            delta_time = min(delta_time, 0.1)
            
            self.simulator.speed_multiplier = self.ui.get_sim_speed()
            self.simulator.tick(delta_time)
            
            # Render UI
            selected_router = self.ui.get_selected_router()
            self.ui.render_continuous(self.graph, self.simulator.packets_in_transit, self.simulator.sim_time, selected_router)
            
            if selected_router and selected_router in self.simulator.nodes:
                self.ui.display_routing_table(selected_router, self.simulator.nodes[selected_router].routing_table)
                
            self.ui.update_sim_time(self.simulator.sim_time)
            
        self.root.after(33, self._tick) # ~30fps
        
    def fail_link(self):
        link_name = self.ui.link_combo.get()
        if not link_name: return
        parts = link_name.split("-")
        if len(parts) != 2: return
        router1, router2 = parts[0].strip(), parts[1].strip()
        
        if self.graph.has_edge(router1, router2):
            self.graph.remove_edge(router1, router2)
            self.simulator.remove_link(router1, router2)
            r1, r2 = min(router1, router2), max(router1, router2)
            self.failed_links.add((r1, r2))
            
            self.ui.update_status(f"Link {link_name} FAILED", "#e74c3c")
            self.ui.recover_link_btn.config(state="normal")
            
    def recover_link(self):
        if not self.failed_links: return
        link_name = self.ui.link_combo.get()
        if not link_name: return
        parts = link_name.split("-")
        router1, router2 = parts[0].strip(), parts[1].strip()
        r1, r2 = min(router1, router2), max(router1, router2)
        
        if (r1, r2) not in self.failed_links: return
        
        cost = 1
        bw = '1Gbps'
        for link in self.config.get('links', []):
            if (link['from'] == router1 and link['to'] == router2) or (link['from'] == router2 and link['to'] == router1):
                cost = link.get('cost', 1)
                bw = link.get('bandwidth', '1Gbps')
                break
                
        self.graph.add_edge(router1, router2, weight=cost)
        self.simulator.add_link(router1, router2, cost, bw)
        self.simulator.trigger_topology_change()
        self.failed_links.remove((r1, r2))
        
        self.ui.update_status(f"Link {link_name} RECOVERED", "#27ae60")
        if not self.failed_links:
            self.ui.recover_link_btn.config(state="disabled")

    def skip_to_converged(self):
        if not self.simulator.is_converging:
            self.ui.show_message("Info", "Network is already converged.", "info")
            return
            
        self.ui.update_status("Skipping to converged state...", "#f39c12")
        self.root.update()
        
        original_speed = self.simulator.speed_multiplier
        self.simulator.speed_multiplier = 1000.0  # Extremely fast speed
        
        max_sim_time = self.simulator.sim_time + 300.0 # Prevent infinite loops
        while self.simulator.is_converging and self.simulator.sim_time < max_sim_time:
            self.simulator.tick(0.05) # Advance 50 sim-seconds per tick
            
        self.simulator.speed_multiplier = original_speed
        
        # Update UI instantly
        selected = self.ui.get_selected_router()
        self.ui.render_continuous(self.graph, self.simulator.packets_in_transit, self.simulator.sim_time, selected)
        if selected and selected in self.simulator.nodes:
            self.ui.display_routing_table(selected, self.simulator.nodes[selected].routing_table)
        self.ui.update_sim_time(self.simulator.sim_time)
        
        if self.simulator.is_converging:
            self.ui.update_status("Timed out waiting for convergence", "#e74c3c")

    def start_file_watcher(self):
        self.file_watcher = JSONFileWatcher(self.config_path, self.reload_network)
        
    def on_closing(self):
        try:
            if self.file_watcher: self.file_watcher.stop()
            time.sleep(0.1)
            self.root.destroy()
        except: pass
        finally: sys.exit(0)

def main():
    script_dir = Path(__file__).parent
    config_path = script_dir / 'network_config.json'
    if not config_path.exists(): sys.exit(1)
    root = tk.Tk()
    app = ProtocolSimulator(root, str(config_path))
    root.mainloop()

if __name__ == "__main__":
    main()
