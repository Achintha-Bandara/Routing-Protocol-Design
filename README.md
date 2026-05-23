# Routing Protocol Design & Simulation

This project implements, simulates, and benchmarks novel routing protocol **Adaptive OSPF (AOSPF)**-in Python. Users can run standalone visual simulators and also measure protocol performance across various network topologies.

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
│   ├── aospf.py
│   ├── ospf.py
│   ├── ospf_no_security.py
│   ├── aospf_with_security.py
│   ├── topology_5.json
│   ├── topology_10.json
│   ├── topology_15.json
│   ├── README.md
├── results/
├── docs/
├── README.md
```

## Protocol Simulators (src/)

Standalone, real-time simulators for each protocol variant:

- **aospf.py** — Adaptive OSPF (AOSPF) with visual database synchronization, optimized LSA flooding, and neighborhood discovery.
- **ospf.py** — Baseline OSPF implementation.
- **aospf_with_security.py** — AOSPF with cryptographic hash adjacency.
- **ospf_no_security.py** — OSPF without security checks, for direct comparison.

*To run a protocol simulator:*
```bash
cd src/protocol_simulation
python aospf.py         # Or replace with desired file
```

Each file is independent with an integrated dashboard for visual feedback.
See the [directory README](src/protocol_simulation/README.md) for more.


## Additional Directories

- **results/**: Experiment outputs
- **docs/**: Supplementary documentation

---

*Developed for EN2150 - Communication Network Engineering*
