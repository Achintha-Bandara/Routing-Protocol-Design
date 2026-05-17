# Routing Protocol Design & Simulation

This project implements and simulates advanced routing protocols with a focus on **Adaptive OSPF (AOSPF)** compared against standard **OSPF** and other variants. It provides real-time visualization of network behavior, LSA flooding, and convergence metrics.

## Prerequisites
- Python 3.10+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Achintha-Bandara/Routing-Protocol-Design.git
cd Routing-Protocol-Design
```

2. Create a virtual environment (recommended):
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Repository Structure

```
Routing-Protocol-Design/
│
├── simulation_files/                 # Visual Protocol Simulators
│   ├── aospf.py                     # Adaptive OSPF simulator (flagship)
│   ├── ospf.py                      # Standard OSPF baseline implementation
│   ├── ospf_with_security.py        # OSPF with security features
│   ├── ospf_no_security.py          # OSPF without security features
│   └── README.md                    # Simulation documentation
│
├── comparison/                       # Protocol Benchmarking Suite
│   ├── main.py                      # Benchmarking GUI launcher
│   ├── protocol_sim/                # Core simulation logic for comparison
│   ├── topology.json                # Default network topology configuration
│   └── README.md                    # Comparison module documentation
│
├── requirements.txt                 # Python dependencies and installation guide
├── README.md                        # This file
└── LICENSE                          # Project license

```

## Execution Guide

### How to Run Visual Simulators

Navigate to the `simulation_files/` directory and run any protocol script directly. These are **standalone** applications and provide the most detailed visual feedback.

```bash
cd simulation_files
python aospf.py  # Recommended for AOSPF analysis
```

**Available simulators:**
- **`aospf.py`**: The flagship simulator for the Adaptive OSPF (AOSPF) protocol.
- **`ospf.py`**: Standard OSPF implementation baseline.
- **`ospf_with_security.py`**: OSPF variant with cryptographic security.
- **`ospf_no_security.py`**: OSPF variant without security for performance comparison.

### How to Run Benchmarking Comparison

To generate performance charts and comparative timing reports (AOSPF vs. OSPF):

```bash
cd comparison
python main.py
```

This will launch the benchmarking GUI and generate comparative analysis across multiple network topologies.

## Dashboard Features

- **Simulation Speed**: Slider to accelerate time (up to 100x) for observing long-term stability
- **Link Control**: Manually fail/recover links to measure exact convergence time
- **Metrics Database**: View persistent logs of synchronization events
- **Performance Charts**: Compare convergence time, message overhead, and CPU load

## Key Metrics Tracked

- **Convergence Time**: Time taken for the network to reach a stable state after a failure
- **Message Overhead**: Total number of protocol packets exchanged
- **CPU Load / Complexity**: Estimated cost of SPF recomputations

---

*Developed for EN2150 - Communication Network Engineering*
