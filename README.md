# Routing Protocol Design & Simulation

This project implements, simulates, and benchmarks advanced routing protocols—including **Adaptive OSPF (AOSPF)**—in Python. Users can run standalone visual simulators and also measure protocol performance across various network topologies.

## Prerequisites

- Python 3.10+
- Dependencies: `networkx`, `matplotlib`, `tkinter`
- Install dependencies:
  ```bash
  pip install networkx matplotlib
  ```

## Repository Structure

```
├── src/
│   ├── protocol_simulation/
│   │   ├── aospf.py
│   │   ├── ospf.py
│   │   ├── ospf_no_security.py
│   │   ├── ospf_with_security.py
│   │   ├── topology.json
│   │   ├── README.md
│   └── protocol_comparison/
│       ├── main.py
│       ├── protocol_sim/
│       ├── topology.json
│       ├── topology_6.json
│       ├── topology_10_complex.json
│       ├── topology_large_20.json
│       ├── topology_aospf_advantage_24.json
│       ├── README.md
├── results/
├── docs/
├── README.md
```

## Protocol Simulators (src/protocol_simulation)

Standalone, real-time simulators for each protocol variant:

- **aospf.py** — Adaptive OSPF (AOSPF) with visual database synchronization, optimized LSA flooding, and neighborhood discovery.
- **ospf.py** — Baseline OSPF implementation.
- **ospf_with_security.py** — OSPF with cryptographic hash adjacency.
- **ospf_no_security.py** — OSPF without security checks, for direct comparison.

*To run a protocol simulator:*
```bash
cd src/protocol_simulation
python aospf.py         # Or replace with desired file
```

Each file is independent with an integrated dashboard for visual feedback.
See the [directory README](src/protocol_simulation/README.md) for more.

## Protocol Performance Benchmark Suite (src/protocol_comparison)

A benchmarking GUI for side-by-side comparisons of OSPF, AOSPF, and other variants. Covers convergence time, message overhead, and CPU cost.

- **main.py:** Run this for the benchmarking interface.
- **protocol_sim/:** Module housing comparative protocol logic.
- Multiple topologies available for scalable tests.

*To run benchmarking:*
```bash
cd src/protocol_comparison
python main.py
```
See the [directory README](src/protocol_comparison/README.md) for more on metrics and usage.

## Additional Directories

- **results/**: Experiment outputs
- **docs/**: Supplementary documentation

---

*Developed for EN2150 - Communication Network Engineering*
