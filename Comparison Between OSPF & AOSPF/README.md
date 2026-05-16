# Protocol Performance Comparison

This module provides a side-by-side performance analysis between standard OSPF and the proposed AOSPF/FALP implementations.

## Overview
Unlike the standalone visualizers in `simulation_files/`, this suite is designed for **benchmarking**. It runs simulations across identical topologies and generates comparative charts.

## Core Components
- **`main.py`**: The entry point to launch the benchmarking GUI.
- **`protocol_sim/`**: contains the protocol logic tailored for comparative measurement.
- **`topology.json`**: The default network structure for testing.

## How to Run
```bash
python main.py
```

## Key Metrics Tracked
- **Convergence Time**: Time taken for the network to reach a stable state after a failure.
- **Message Overhead**: Total number of protocol packets exchanged.
- **CPU Load / Complexity**: Estimated cost of SPF recomputations.
