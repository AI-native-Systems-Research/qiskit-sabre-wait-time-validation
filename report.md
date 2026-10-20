# SABRE wait-time correctness

**PASS** — 96/96 cases; 2/2 self-checks.

Revision: `72efe50ac12bd949970456cd59c46eaa812b3a72`. Seeds: `[0, 1, 42, 2, 7, 123]`.
Run: 2026-10-20T16:00:42+00:00. Qiskit 2.6.0.dev0+72efe50; Python 3.11.8.

16 circuits, 10 qubits each; bidirectional line, trivial layout, one routing trial.
Each output must match its original unitary (layout-aware, global phase kept, default tolerances), preserve width and layout metadata, and satisfy connectivity.

| Circuit | Passed |
|---|---|
| qft10 | 6/6 |
| random10x60 | 6/6 |
| adder4 | 6/6 |
| ring10 | 6/6 |
| qv10 | 6/6 |
| dtc10 | 6/6 |
| random10x20 | 6/6 |
| random10x40 | 6/6 |
| qv10_seed7 | 6/6 |
| bv10 | 6/6 |
| bvlike10 | 6/6 |
| trotter10 | 6/6 |
| qaoa10 | 6/6 |
| grover10 | 6/6 |
| mcx10 | 6/6 |
| modular_adder10 | 6/6 |

Self-checks:

- Ignored layout detected: PASS
- Extra X gate detected: PASS

Scope: routing-only checks on these circuits and seeds, not a general proof. Raw results and build path: `results/results.jsonl`.
