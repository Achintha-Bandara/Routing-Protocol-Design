# OSPF Protocol Simulator

A lightweight, interactive OSPF (Open Shortest Path First) protocol simulator with automatic JSON configuration reloading.

## Features

✅ **Automatic JSON Reloading** - Network topology updates instantly when you modify `network_config.json`  
✅ **OSPF Routing Calculation** - Uses Dijkstra's algorithm (SPF) to calculate shortest paths  
✅ **Network Visualization** - Interactive graph display of network topology  
✅ **Routing Table Display** - View calculated routes from any router  
✅ **Clean & Minimal** - Only 4 essential files needed  
✅ **Protocol Abstraction** - Protocol logic separated from UI  

## Project Structure

```
ospf/
├── main.py                 # Entry point with JSON file watcher
├── protocol.py             # OSPF engine and topology manager
├── ui.py                   # User interface components
├── network_config.json     # Network topology configuration
└── README.md              # This file
```

## Requirements

- Python 3.8+
- tkinter (usually included with Python)
- networkx
- matplotlib

## Installation

Install required packages:

```bash
pip install networkx matplotlib
```

## Quick Start

1. **Edit network topology** in `network_config.json`:

```json
{
  "network": {
    "name": "Sample OSPF Network",
    "description": "6-Router example topology",
    "ensure_connectivity": true,
    "version": "1.0"
  },
  "routers": [
    {
      "id": "R1",
      "name": "Router 1 - Core",
      "area": "0.0.0.0",
      "region": "Central"
    },
    {
      "id": "R2",
      "name": "Router 2 - Branch A",
      "area": "0.0.0.0",
      "region": "North"
    }
  ],
  "links": [
    {
      "from": "R1",
      "to": "R2",
      "cost": 2
    }
  ]
}
```

2. **Run the simulator**:

```bash
python main.py
```

3. **Modify the JSON** and changes apply automatically (no restart needed!)

## Usage

### Network Topology Tab

1. Select a source router from the dropdown
2. Click **▶ Run OSPF Calculation**
3. View the network graph and routing costs

### Routing Tables Tab

1. Select a router from the left panel
2. View its complete routing table with destination costs
3. Shows all learned routes for that router

## Configuration File (network_config.json)

### Required Fields

**Network Object:**
- `name` (string) - Network name
- `description` (string) - Network description
- `version` (string) - Configuration version

**Routers Array:**
- `id` (string) - Unique router identifier (e.g., "R1", "R2")
- `name` (string) - Router display name
- `area` (string) - OSPF area (default: "0.0.0.0")
- `region` (string) - Geographic region (optional)

**Links Array:**
- `from` (string) - Source router ID
- `to` (string) - Destination router ID
- `cost` (integer) - Link cost/metric (1-10000)

### Example Configuration

See `network_config.json` for a complete 6-router network example.

## How It Works

### Auto-Reload Mechanism

The application continuously monitors `network_config.json` for changes:
- **File Watcher Thread**: Runs in background checking file modification time
- **Instant Reload**: When JSON changes, topology is automatically reloaded
- **User Notification**: Popup confirms when configuration is reloaded

### OSPF Protocol Implementation

**SPF (Shortest Path First) Calculation:**
- Uses Dijkstra's algorithm to find shortest paths
- Calculates routing table for selected source router
- Edge weights = link costs

**Algorithm:**
```
1. Select source router
2. For each destination router:
   - Calculate shortest path using Dijkstra
   - Store path cost in routing table
3. Display results
```

## File Reference

### main.py
**Entry point and coordinator**
- `ConfigLoader`: Loads and validates JSON configuration
- `JSONFileWatcher`: Monitors file changes in background thread
- `OSPFSimulator`: Main application class orchestrating UI and protocol

### protocol.py
**OSPF Protocol Logic**
- `OSPFEngine`: Core OSPF calculation engine
  - `calculate_shortest_paths()` - SPF for single router
  - `calculate_all_routing_tables()` - SPF for all routers
- `NetworkTopologyManager`: Converts JSON config to graph
  - `create_from_config()` - Builds NetworkX graph from JSON

### ui.py
**User Interface**
- `OSPFSimulatorUI`: Main window and tab management
  - `setup_topology_tab()` - Network visualization
  - `setup_routing_tab()` - Routing table display
  - `draw_topology()` - Matplotlib graph rendering

### network_config.json
**Network Configuration**
- Complete topology definition
- Easy to edit and modify
- Auto-loaded on application start
- Changes trigger auto-reload

## Modifying the Network

### Add a New Router

Edit `network_config.json`:

```json
{
  "id": "R7",
  "name": "Router 7 - New Branch",
  "area": "0.0.0.0",
  "region": "East"
}
```

**Application automatically detects and loads it.**

### Change Link Costs

```json
{
  "from": "R1",
  "to": "R2",
  "cost": 5
}
```

**OSPF routes recalculate automatically.**

### Add Link Between Routers

```json
{
  "from": "R3",
  "to": "R5",
  "cost": 3
}
```

**Network topology updates instantly.**

## Troubleshooting

### "Configuration file not found"
- Ensure `network_config.json` exists in the same directory as `main.py`

### "Invalid JSON in configuration file"
- Check for syntax errors in `network_config.json`
- Use JSON validator: https://jsonlint.com

### "Must have at least 2 routers"
- Configuration requires minimum 2 routers
- Add more routers to `routers` array

### "Invalid router reference in link"
- Ensure `from` and `to` values match router `id` values
- Check for typos in router IDs

### UI doesn't update after JSON change
- Check console for error messages
- Wait 1-2 seconds (file watcher checks every second)
- Ensure JSON is valid after editing

## Performance Notes

- **Small Networks** (2-10 routers): < 1ms SPF calculation
- **Medium Networks** (10-50 routers): 1-10ms SPF calculation
- **Large Networks** (50+ routers): May take 50-100ms

## Future Enhancements

Possible improvements:
- Multi-area OSPF support
- Link failure simulation
- Real-time convergence visualization
- Export routing tables to CSV
- Import topology from other formats

## License

This project is provided as-is for educational purposes.

## Author

OSPF Protocol Simulator - CNE Protocol Design Project

---

**Tips:**
- Modify `network_config.json` while the app is running
- Changes apply automatically (no restart needed)
- Try changing link costs to see routing recalculate
- Use meaningful router names for better visualization
