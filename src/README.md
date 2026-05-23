# Visual Protocol Simulations

This directory contains standalone, real-time discrete event simulators. Each file implements a specific version of a routing protocol with an integrated dashboard.

## Important Note
Each simulation file in this directory is **independent** and should be run separately.

## Available Simulators

### 1. Adaptive OSPF (AOSPF) - `aospf.py`
The primary research implementation. 
- Features optimized LSA flooding and persistent convergence metrics.
- Visualizes real-time database synchronization and neighborhood discovery.

### 2. Standard OSPF - `ospf.py`
The baseline implementation for comparison.
- Uses standard OSPF timers.
- Standard flooding mechanisms.

### 3. Security Variants
- **`aospf_with_security.py`**: Implementation with cryptographic hash verification for adjacency.
- **`ospf_no_security.py`**: Implementation with security features disabled for performance comparison.

## How to Run
Run any file using Python:

```bash
python aospf.py
```

## Dashboard Features
- **Simulation Speed**: Slider to accelerate time (up to 100x) for observing long-term stability.
- **Link Control**: Manually fail/recover links to measure exact convergence time.
- **Metrics Database**: View persistent logs of synchronization events.
