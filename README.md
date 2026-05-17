# Routing Protocol Design & Simulation

This project implements and simulates advanced routing protocols with a focus on **Adaptive OSPF (AOSPF)** compared against standard **OSPF** and other variants. It provides real-time visualization, convergence metrics, and performance benchmarking.

## Prerequisites
- Python 3.10+
- Dependencies: `networkx`, `matplotlib`, `tkinter`

```bash
pip install networkx matplotlib
```

## Repository Structure

### 1. Visual Simulations (`/simulation_files`)
This directory contains the primary interactive GUI-based simulators for different protocol states. Each file is a standalone application that allows you to observe LSA flooding, database synchronization, and recovery timing.

- **`aospf.py`**: The flagship simulator for the Adaptive OSPF (AOSPF) protocol.
- **`ospf.py`**: Standard OSPF implementation baseline.
- **`ospf_with_security.py` / `ospf_no_security.py`**: OSPF variants focused on secure vs. non-secure adjacency forming.

### 2. Protocol Comparison (`/comparison`)
A benchmarking suite designed to compare OSPF against AOSPF/FALP across various topologies.

- **`main.py`**: Launches the comparison GUI.
- **`protocol_sim/`**: The core simulation logic for the comparison engine.

## Execution Guide

### How to Run Visual Simulators
Navigate to the `simulation_files/` directory and run any protocol script directly. These are **standalone** and provide the most detailed visual feedback.

```powershell
cd "simulation_files"
python aospf.py  # Recommended for AOSPF analysis
```

### How to Run Benchmarking Comparison
To generate performance charts and comparative timing reports (AOSPF vs. OSPF):

```bash
git clone https://github.com/Achintha-Bandara/Routing-Protocol-Design.git
cd Routing-Protocol-Design/comparison
python main.py
```

---
*Developed for EN2150 - Communication Network Engineering*
