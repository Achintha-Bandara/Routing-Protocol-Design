# OSPF vs FALP Protocol Comparison

This project simulates an OSPF-like baseline and a proposed faster link-state protocol called FALP (Fast Adaptive Link-state Protocol).

The comparison is topology-driven. Edit [topology.json](topology.json) and rerun the app; the charts, timing, and report update from the changed topology automatically.

## What FALP changes

- It limits flooding to the impacted neighborhood instead of the full routing domain.
- It uses incremental recomputation instead of rebuilding the full SPF tree everywhere.
- It keeps unaffected routers out of the recovery path, which lowers message and CPU cost.

## Trade-offs

- Faster convergence and lower control overhead.
- More complexity in locality detection and state tracking.
- Harder to standardize and debug than a plain OSPF-style design.

## Run

```bash
python main.py
```
