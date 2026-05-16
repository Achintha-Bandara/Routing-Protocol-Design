"""
Protocol Simulator - Main Entry Point
Supports OSPF, BGP, IS-IS, and RIP protocols
Automatically reloads network topology when JSON configuration file changes
"""
import tkinter as tk
from tkinter import messagebox
import json
import os
import sys
import threading
import time
from pathlib import Path
import networkx as nx

# ====== PROTOCOL SELECTION ======
# Change this to switch protocols: 'ospf', 'bgp', 'isis', 'rip'
PROTOCOL_NAME = 'rip'
# ================================

# Dynamic protocol import
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
    """Load and validate network configuration from JSON"""
    
    @staticmethod
    def load_config(config_path):
        """Load configuration from JSON file"""
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
        """Validate configuration structure"""
        required_fields = ['network', 'routers', 'links']
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field in config: {field}")
        
        network = config['network']
        if 'name' not in network or 'description' not in network:
            raise ValueError("Network must have 'name' and 'description'")
        
        routers = config['routers']
        if not isinstance(routers, list) or len(routers) < 2:
            raise ValueError("Must have at least 2 routers")
        
        for router in routers:
            if 'id' not in router or 'name' not in router:
                raise ValueError("Each router must have 'id' and 'name'")
        
        links = config['links']
        if not isinstance(links, list):
            raise ValueError("Links must be a list")
        
        router_ids = {r['id'] for r in routers}
        for link in links:
            if 'from' not in link or 'to' not in link or 'cost' not in link:
                raise ValueError("Each link must have 'from', 'to', and 'cost'")
            
            if link['from'] not in router_ids or link['to'] not in router_ids:
                raise ValueError(f"Invalid router reference in link: {link}")


class JSONFileWatcher:
    """Watches JSON configuration file for changes"""
    
    def __init__(self, config_path, callback):
        """
        Initialize file watcher
        
        Args:
            config_path: Path to JSON file to watch
            callback: Function to call when file changes
        """
        self.config_path = config_path
        self.callback = callback
        self.last_modified = os.path.getmtime(config_path) if os.path.exists(config_path) else None
        self.running = True
        self.watch_thread = threading.Thread(target=self._watch_file, daemon=True)
        self.watch_thread.start()
    
    def _watch_file(self):
        """Watch file for modifications"""
        while self.running:
            try:
                if os.path.exists(self.config_path):
                    current_modified = os.path.getmtime(self.config_path)
                    
                    if self.last_modified is not None and current_modified > self.last_modified:
                        self.last_modified = current_modified
                        time.sleep(0.5)  # Small delay to ensure file is fully written
                        self.callback()
                    elif self.last_modified is None:
                        self.last_modified = current_modified
            except Exception as e:
                print(f"Error watching file: {e}")
            
            time.sleep(1)  # Check every second
    
    def stop(self):
        """Stop watching file"""
        self.running = False


class NetworkTopologyManager:
    """Manages network topology creation from configuration"""
    
    @staticmethod
    def create_from_config(graph, config):
        """
        Create network graph from JSON configuration
        
        Args:
            graph: NetworkX graph to populate
            config: Configuration dictionary from JSON
        """
        graph.clear()
        
        # Add all routers as nodes
        routers = config.get('routers', [])
        for router in routers:
            router_id = router.get('id')
            router_name = router.get('name', '')
            area = router.get('area', '0.0.0.0')
            
            graph.add_node(router_id, name=router_name, area=area)
        
        # Add all links as edges
        links = config.get('links', [])
        for link in links:
            from_router = link.get('from')
            to_router = link.get('to')
            cost = link.get('cost', 1)
            
            if from_router and to_router:
                graph.add_edge(from_router, to_router, weight=cost)
    
    @staticmethod
    def get_network_info(config):
        """Get network information from configuration"""
        network = config.get('network', {})
        return {
            'name': network.get('name', 'Network'),
            'description': network.get('description', ''),
            'version': network.get('version', '1.0'),
            'num_routers': len(config.get('routers', [])),
            'num_links': len(config.get('links', []))
        }


class ProtocolSimulator:
    """Main Protocol Simulator application with auto-reload"""
    
    def __init__(self, root, config_path):
        self.root = root
        self.config_path = config_path
        self.config = None
        self.graph = nx.Graph()
        self.protocol_engine = ProtocolEngine()
        self.ui = None
        self.file_watcher = None
        self.updating = False
        self.all_routing_tables = {}
        
        # Load initial configuration
        self.load_configuration()
        
        # Setup UI
        self.setup_ui()
        
        # Start file watcher
        self.start_file_watcher()
        
        # Handle window closure
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_configuration(self):
        """Load configuration from JSON file"""
        try:
            self.config = ConfigLoader.load_config(self.config_path)
            print(f"[OK] Configuration loaded: {self.config_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Error loading configuration: {e}")
            self.config = None
            return False
    
    def reload_network(self):
        """Reload network from updated JSON configuration"""
        if self.updating:
            return
        
        self.updating = True
        
        try:
            # Load new configuration
            if not self.load_configuration():
                self.updating = False
                return
            
            # Schedule UI update on main thread
            self.root.after(0, self._perform_ui_update)
        except Exception as e:
            print(f"[ERROR] Error reloading network: {e}")
            self.updating = False
    
    def _perform_ui_update(self):
        """Perform UI update on main thread (called via root.after)"""
        try:
            # Update UI (which will also update graph)
            self.update_ui()
            
            # Show notification
            if self.ui:
                network_info = NetworkTopologyManager.get_network_info(self.config)
                self.ui.update_status(
                    f"[OK] Configuration reloaded: {network_info['num_routers']} routers, "
                    f"{network_info['num_links']} links",
                    "#27ae60"
                )
                self.ui.show_message("Configuration Updated", 
                                    "Network topology has been reloaded from JSON file")
                print("[OK] Network topology reloaded successfully")
        except Exception as e:
            print(f"[ERROR] Error updating UI: {e}")
            if self.ui:
                self.ui.show_message("Error", f"Failed to reload network: {e}", "error")
        finally:
            self.updating = False
    
    def setup_ui(self):
        """Setup and initialize UI"""
        network_info = NetworkTopologyManager.get_network_info(self.config) if self.config else None
        self.ui = OSPFSimulatorUI(self.root, network_info, protocol_name=PROTOCOL_NAME.upper())
        
        # Populate initial data
        if self.config:
            self.update_ui()
        
        # Bind button clicks
        self.ui.run_ospf_btn.config(command=self.run_protocol)
        self.ui.fail_link_btn.config(command=self.fail_link)
        self.ui.recover_link_btn.config(command=self.recover_link)
        self.ui.router_listbox.bind('<<ListboxSelect>>', self.on_router_select)
        
        # Track failed links
        self.failed_links = set()
    
    def update_ui(self):
        """Update UI with current configuration"""
        if not self.config:
            return
        
        # Create graph from configuration
        NetworkTopologyManager.create_from_config(self.graph, self.config)
        
        # Update network info
        network_info = NetworkTopologyManager.get_network_info(self.config)
        routers = self.config.get('routers', [])
        
        self.ui.update_topology_info(network_info, routers)
        self.ui.draw_topology(self.graph)
        self.ui.update_router_list(routers)
        
        # Update source router combo
        router_ids = [r['id'] for r in routers]
        self.ui.source_combo['values'] = router_ids
        if router_ids:
            self.ui.source_combo.current(0)
        
        # Update link combo
        links = self.config.get('links', [])
        link_names = [f"{link['from']}-{link['to']}" for link in links]
        self.ui.link_combo['values'] = link_names
        if link_names:
            self.ui.link_combo.current(0)
        
        # Reset failed links when topology is reloaded
        self.failed_links = set()
        self.ui.fail_link_btn.config(state="normal")
        self.ui.recover_link_btn.config(state="disabled")
    
    def run_protocol(self):
        """Run selected protocol routing calculation and animate"""
        source_router = self.ui.source_combo.get()
        
        if not source_router:
            self.ui.show_message("Warning", "Please select a source router", "warning")
            return
        
        try:
            import time as time_module
            start_time = time_module.time()
            
            # Get protocol-specific info
            protocol_info = self.protocol_engine.get_protocol_info()
            
            # Estimate convergence time based on topology
            is_recon = getattr(self, 'has_converged_once', False)
            estimated_time = self.protocol_engine.estimate_convergence_time(self.graph, is_reconvergence=is_recon)
            self.has_converged_once = True
            self.ui.update_estimated_convergence_time(estimated_time)
            
            self.ui.update_status(f"Calculating {PROTOCOL_NAME.upper()} routes ({protocol_info['convergence_desc']})...", "#f39c12")
            self.root.update()
            
            # Calculate routing tables for ALL routers
            all_routing_tables = self.protocol_engine.calculate_all_routing_tables(self.graph)
            
            # Calculate elapsed time
            elapsed_time = time_module.time() - start_time
            
            # Store for later access
            self.all_routing_tables = all_routing_tables
            
            # Display first router's routing table
            if all_routing_tables:
                first_router = sorted(all_routing_tables.keys())[0]
                self.ui.display_routing_table(first_router, all_routing_tables[first_router])
            
            # Show convergence log
            log = self.protocol_engine.get_convergence_log()
            print(f"\n{PROTOCOL_NAME.upper()} Convergence Log:")
            print(f"Protocol: {protocol_info['message_type']} - {protocol_info['description']}")
            for entry in log[-5:]:
                print(f"  {entry}")
            
            # Update status
            status_msg = f"[OK] {PROTOCOL_NAME.upper()} calculated from {source_router}"
            self.ui.update_status(status_msg, "#27ae60")
            
            # Auto-animate after calculation with protocol-specific animation
            self._start_animation_after_delay(source_router, protocol_info)
        
        except Exception as e:
            self.ui.show_message("Error", f"Error calculating {PROTOCOL_NAME.upper()}: {e}", "error")
            self.ui.update_status(f"Error during {PROTOCOL_NAME.upper()} calculation", "#e74c3c")
    
    def _start_animation_after_delay(self, source_router, protocol_info):
        """Start protocol-specific animation after a short delay"""
        self.root.after(500, self._animate_protocol_messages, source_router, protocol_info)
    
    def _animate_protocol_messages(self, source_router, protocol_info):
        """Animate protocol-specific messages from selected source router"""
        if self.ui.animation_running:
            return
        
        routers = list(self.graph.nodes())
        if not routers:
            return
        
        # Update status before animation
        message_type = 'Shortest Path Tree'
        self.ui.update_status(
            f"{PROTOCOL_NAME.upper()} Animation: Displaying {message_type}...", 
            "#3498db"
        )
        
        # Pass protocol info to animation
        self.ui.animate_protocol_on_topology(self.graph, routers, source_router, protocol_info)
        self.ui.update_status(f"{PROTOCOL_NAME.upper()} Animation: Displaying shortest paths...", "#3498db")
    
    def fail_link(self):
        """Fail a selected link in the network"""
        link_name = self.ui.link_combo.get()
        if not link_name:
            self.ui.show_message("Warning", "Please select a link first", "warning")
            return
        
        # Parse link name (e.g., "R1-R2")
        parts = link_name.split("-")
        if len(parts) != 2:
            return
        
        router1, router2 = parts[0].strip(), parts[1].strip()
        
        try:
            # Remove edge from graph
            if self.graph.has_edge(router1, router2):
                self.graph.remove_edge(router1, router2)
                # Store normalized edge tuple
                r1, r2 = min(router1, router2), max(router1, router2)
                self.failed_links.add((r1, r2))
                
                # Update UI
                self.ui.draw_topology(self.graph, recalculate_pos=False)
                self.ui.update_status(f"Link {link_name} FAILED", "#e74c3c")
                self.ui.recover_link_btn.config(state="normal")
                
                # Recalculate routes
                protocol_info = self.protocol_engine.get_protocol_info()
                estimated_time = self.protocol_engine.estimate_convergence_time(self.graph, is_reconvergence=True)
                self.has_converged_once = True
                self.ui.update_estimated_convergence_time(estimated_time)
                
                all_routing_tables = self.protocol_engine.calculate_all_routing_tables(self.graph)
                self.all_routing_tables = all_routing_tables
                
                print(f"[LINK FAILURE] {link_name} removed from topology")
            else:
                self.ui.show_message("Error", f"Link {link_name} not found in topology", "error")
        except Exception as e:
            self.ui.show_message("Error", f"Error failing link: {e}", "error")
    
    def recover_link(self):
        """Recover a failed link in the network"""
        if not self.failed_links:
            self.ui.show_message("Info", "No failed links to recover", "warning")
            return
        
        link_name = self.ui.link_combo.get()
        if not link_name:
            return
            
        parts = link_name.split("-")
        if len(parts) != 2:
            return
            
        router1, router2 = parts[0].strip(), parts[1].strip()
        r1, r2 = min(router1, router2), max(router1, router2)
        
        if (r1, r2) not in self.failed_links:
            self.ui.show_message("Info", f"Link {link_name} is not currently failed", "warning")
            return
            
        try:
            # Find the original edge data
            cost = 1
            for link in self.config.get('links', []):
                if (link['from'] == router1 and link['to'] == router2) or \
                   (link['from'] == router2 and link['to'] == router1):
                    cost = link.get('cost', 1)
                    break
                    
            self.graph.add_edge(router1, router2, weight=cost)
            self.failed_links.remove((r1, r2))
            
            # Update UI
            self.ui.draw_topology(self.graph, recalculate_pos=False)
            self.ui.update_status(f"Link {link_name} RECOVERED", "#27ae60")
            if not self.failed_links:
                self.ui.recover_link_btn.config(state="disabled")
            
            # Recalculate routes
            protocol_info = self.protocol_engine.get_protocol_info()
            estimated_time = self.protocol_engine.estimate_convergence_time(self.graph, is_reconvergence=True)
            self.has_converged_once = True
            self.ui.update_estimated_convergence_time(estimated_time)
            
            all_routing_tables = self.protocol_engine.calculate_all_routing_tables(self.graph)
            self.all_routing_tables = all_routing_tables
            
            print(f"[LINK RECOVERY] {link_name} restored to topology")
        except Exception as e:
            self.ui.show_message("Error", f"Error recovering link: {e}", "error")
    
    def on_router_select(self, event):
        """Handle router selection in listbox"""
        selection = self.ui.router_listbox.curselection()
        if not selection:
            return
        
        router_id = self.ui.router_listbox.get(selection[0]).split(" ")[0]
        
        # Display routing table for selected router
        if hasattr(self, 'all_routing_tables'):
            routing_table = self.all_routing_tables.get(router_id, {})
            self.ui.display_routing_table(router_id, routing_table)
        else:
            self.ui.show_message("Info", f"Click 'Run {PROTOCOL_NAME.upper()}' first to see routing tables", "warning")
    
    def start_file_watcher(self):
        """Start watching JSON file for changes"""
        self.file_watcher = JSONFileWatcher(self.config_path, self.reload_network)
        print(f"[OK] File watcher started for: {self.config_path}")
    
    def on_closing(self):
        """Cleanup and close application"""
        try:
            if self.file_watcher:
                self.file_watcher.stop()
            self.ui.animation_running = False  # Stop any running animations
            time.sleep(0.2)  # Brief delay for threads to stop
            self.root.destroy()
        except:
            pass
        finally:
            sys.exit(0)


def main():
    """Main entry point"""
    # Find configuration file
    script_dir = Path(__file__).parent
    config_path = script_dir / 'network_config.json'
    
    if not config_path.exists():
        # Create default config if not found
        print(f"No configuration file found at {config_path}")
        print("Please create a 'network_config.json' file in the same directory as this script")
        sys.exit(1)
    
    # Create and run application
    root = tk.Tk()
    app = ProtocolSimulator(root, str(config_path))
    
    print("\n" + "="*60)
    print(f"{PROTOCOL_NAME.upper()} Protocol Simulator")
    print("="*60)
    print(f"Configuration file: {config_path}")
    print(f"Protocol: {PROTOCOL_NAME.upper()}")
    print("File watching enabled - changes to JSON will auto-reload")
    print("="*60 + "\n")
    
    root.mainloop()


if __name__ == "__main__":
    main()

