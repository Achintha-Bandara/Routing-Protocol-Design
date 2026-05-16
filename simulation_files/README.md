# Routing Protocol Discrete Event Simulator

A real-time, discrete event simulation engine for visualizing and analyzing network routing protocols (OSPF, RIP, BGP, IS-IS).

## Features
- **Continuous Discrete Event Simulation**: Protocols run continuously, sending simulated packets over links based on actual configurable bandwidths.
- **Protocol Implementations**:
  - **OSPF**: Link-State DB, LSA flooding, 10s Hello / 40s Dead timers, SPF throttling.
  - **RIP**: Distance-Vector logic, Split-Horizon, 30s updates, 180s Invalid / 240s Flush timers.
  - **BGP**: Path-Vector logic, AS_PATH loop prevention, MRAI batching (5s), Keepalives (60s).
  - **IS-IS**: LSP flooding, fast SPF, 10s Hello / 30s Hold timers.
- **Simulation Speed Control**: Scale time from 0.1x to 100x speed to observe long-tail convergence events (like RIP's 180s timeout) quickly.
- **Exact Convergence Timing**: Measures the exact simulated time from a link failure until all network nodes have fully synchronized their routing tables.

## Prerequisites
- Python 3.13 or newer
- `networkx`
- `matplotlib`

You can install dependencies using:
```bash
pip install networkx matplotlib
```

## How to Run
1. Navigate to the `simulation_files` directory.
2. Edit `main.py` and change the `PROTOCOL_NAME` variable (around Line 14) to select your protocol (`ospf`, `rip`, `bgp`, `isis`).
3. Run the script:
   ```bash
   python main.py
   ```

## Usage
- **Simulation Speed**: Use the slider on the left to speed up or slow down the simulation time. This is especially useful for RIP or BGP, which have long timer intervals. (At 100x speed, a 180-second timeout takes 1.8 seconds of real time).
- **Topology Configuration**: The network topology is controlled via `network_config.json`. You can edit this file to add/remove routers or change link bandwidths/costs. The application watches this file and will **automatically reload** the simulation if you save changes!
- **Link Failures**: Select a link from the "Link Control" dropdown and click **Fail Link**. Watch the convergence time tracker to see exactly how long the protocol takes to recover based on its timers.
- **Routing Tables**: Select any router from the "Routing Tables" tab to view its real-time formatted routing table. Click a router in the list to highlight its current Shortest Path Tree in orange on the topology map.
