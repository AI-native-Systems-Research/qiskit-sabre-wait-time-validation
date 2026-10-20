# SABRE wait-time heuristic: routing correctness check

- Revision `72efe50ac12bd949970456cd59c46eaa812b3a72`; build `/Users/ophir/PycharmProjects/qiskit-evolved/qiskit/_accelerate.cpython-311-darwin.so`; qiskit 2.6.0.dev0+72efe50, Python 3.11.8, macOS-27.0-arm64-arm-64bit
- Run 2026-10-20T15:05:54+00:00; seeds [0, 1, 42]; coupling map line(10); trials 1; trivial initial layout; heuristics ['decay', 'wait_time']
- Check per case: `Operator.from_circuit(out) == Operator.from_circuit(qc)` (layout-aware, global phase kept) and every two-qubit gate on a coupling edge

## Result: PASS — 36/36 cases, 2/2 self-checks

## Per-fixture results
| fixture | input ops | input depth | heuristic | seed | swaps | depth before decomp | D2 after SWAP decomp | N2 after SWAP decomp | final perm changed | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| qft10 | 55 | 19 | decay | 0 | 44 | 44 | 72 | 177 | True | yes |
| qft10 | 55 | 19 | wait_time | 0 | 43 | 42 | 65 | 174 | True | yes |
| qft10 | 55 | 19 | decay | 1 | 44 | 48 | 83 | 177 | True | yes |
| qft10 | 55 | 19 | wait_time | 1 | 43 | 44 | 69 | 174 | True | yes |
| qft10 | 55 | 19 | decay | 42 | 46 | 44 | 78 | 183 | True | yes |
| qft10 | 55 | 19 | wait_time | 42 | 43 | 42 | 65 | 174 | True | yes |
| random10x60 | 429 | 60 | decay | 0 | 292 | 284 | 488 | 1081 | True | yes |
| random10x60 | 429 | 60 | wait_time | 0 | 265 | 262 | 445 | 1000 | True | yes |
| random10x60 | 429 | 60 | decay | 1 | 309 | 301 | 517 | 1132 | True | yes |
| random10x60 | 429 | 60 | wait_time | 1 | 299 | 285 | 477 | 1102 | True | yes |
| random10x60 | 429 | 60 | decay | 42 | 272 | 278 | 472 | 1021 | True | yes |
| random10x60 | 429 | 60 | wait_time | 42 | 291 | 277 | 460 | 1078 | True | yes |
| adder4 | 176 | 99 | decay | 0 | 27 | 126 | 109 | 162 | True | yes |
| adder4 | 176 | 99 | wait_time | 0 | 27 | 126 | 109 | 162 | True | yes |
| adder4 | 176 | 99 | decay | 1 | 27 | 126 | 109 | 162 | True | yes |
| adder4 | 176 | 99 | wait_time | 1 | 27 | 126 | 109 | 162 | True | yes |
| adder4 | 176 | 99 | decay | 42 | 27 | 126 | 109 | 162 | True | yes |
| adder4 | 176 | 99 | wait_time | 42 | 27 | 126 | 109 | 162 | True | yes |
| ring10 | 310 | 41 | decay | 0 | 91 | 84 | 118 | 373 | True | yes |
| ring10 | 310 | 41 | wait_time | 0 | 90 | 85 | 129 | 370 | True | yes |
| ring10 | 310 | 41 | decay | 1 | 91 | 85 | 118 | 373 | True | yes |
| ring10 | 310 | 41 | wait_time | 1 | 88 | 83 | 120 | 364 | True | yes |
| ring10 | 310 | 41 | decay | 42 | 90 | 81 | 114 | 370 | True | yes |
| ring10 | 310 | 41 | wait_time | 42 | 89 | 85 | 121 | 367 | True | yes |
| qv10 | 50 | 10 | decay | 0 | 91 | 59 | 143 | 323 | True | yes |
| qv10 | 50 | 10 | wait_time | 0 | 74 | 50 | 118 | 272 | True | yes |
| qv10 | 50 | 10 | decay | 1 | 83 | 52 | 128 | 299 | True | yes |
| qv10 | 50 | 10 | wait_time | 1 | 74 | 50 | 118 | 272 | True | yes |
| qv10 | 50 | 10 | decay | 42 | 81 | 50 | 117 | 293 | True | yes |
| qv10 | 50 | 10 | wait_time | 42 | 83 | 51 | 127 | 299 | True | yes |
| dtc10 | 29 | 4 | decay | 0 | 0 | 4 | 2 | 9 | False | yes |
| dtc10 | 29 | 4 | wait_time | 0 | 0 | 4 | 2 | 9 | False | yes |
| dtc10 | 29 | 4 | decay | 1 | 0 | 4 | 2 | 9 | False | yes |
| dtc10 | 29 | 4 | wait_time | 1 | 0 | 4 | 2 | 9 | False | yes |
| dtc10 | 29 | 4 | decay | 42 | 0 | 4 | 2 | 9 | False | yes |
| dtc10 | 29 | 4 | wait_time | 42 | 0 | 4 | 2 | 9 | False | yes |

## decay vs wait_time on the same build (informational, not pass/fail)
Off = decay; on = wait_time. D2 is two-qubit depth and N2 is two-qubit gate count, both measured after expanding every SWAP into three CX gates. Directives are excluded. Other gates retain their existing definitions and no optimization follows decomposition. Differences are on - off; negative means improvement.

| fixture | seed | D2 off | D2 on | ΔD2 | N2 off | N2 on | ΔN2 |
|---|---|---|---|---|---|---|---|
| adder4 | 0 | 109 | 109 | 0 | 162 | 162 | 0 |
| adder4 | 1 | 109 | 109 | 0 | 162 | 162 | 0 |
| adder4 | 42 | 109 | 109 | 0 | 162 | 162 | 0 |
| dtc10 | 0 | 2 | 2 | 0 | 9 | 9 | 0 |
| dtc10 | 1 | 2 | 2 | 0 | 9 | 9 | 0 |
| dtc10 | 42 | 2 | 2 | 0 | 9 | 9 | 0 |
| qft10 | 0 | 72 | 65 | -7 | 177 | 174 | -3 |
| qft10 | 1 | 83 | 69 | -14 | 177 | 174 | -3 |
| qft10 | 42 | 78 | 65 | -13 | 183 | 174 | -9 |
| qv10 | 0 | 143 | 118 | -25 | 323 | 272 | -51 |
| qv10 | 1 | 128 | 118 | -10 | 299 | 272 | -27 |
| qv10 | 42 | 117 | 127 | 10 | 293 | 299 | 6 |
| random10x60 | 0 | 488 | 445 | -43 | 1081 | 1000 | -81 |
| random10x60 | 1 | 517 | 477 | -40 | 1132 | 1102 | -30 |
| random10x60 | 42 | 472 | 460 | -12 | 1021 | 1078 | 57 |
| ring10 | 0 | 118 | 129 | 11 | 373 | 370 | -3 |
| ring10 | 1 | 118 | 120 | 2 | 373 | 364 | -9 |
| ring10 | 42 | 114 | 121 | 7 | 370 | 367 | -3 |

### SWAP count and original routed depth (before decomposition)
SWAPs with wait_time: fewer in 10, equal in 6, more in 2 of 18 pairs.

| fixture | seed | swaps decay | swaps wait_time | Δ swaps | depth decay | depth wait_time | Δ depth |
|---|---|---|---|---|---|---|---|
| adder4 | 0 | 27 | 27 | 0 | 126 | 126 | 0 |
| adder4 | 1 | 27 | 27 | 0 | 126 | 126 | 0 |
| adder4 | 42 | 27 | 27 | 0 | 126 | 126 | 0 |
| dtc10 | 0 | 0 | 0 | 0 | 4 | 4 | 0 |
| dtc10 | 1 | 0 | 0 | 0 | 4 | 4 | 0 |
| dtc10 | 42 | 0 | 0 | 0 | 4 | 4 | 0 |
| qft10 | 0 | 44 | 43 | -1 | 44 | 42 | -2 |
| qft10 | 1 | 44 | 43 | -1 | 48 | 44 | -4 |
| qft10 | 42 | 46 | 43 | -3 | 44 | 42 | -2 |
| qv10 | 0 | 91 | 74 | -17 | 59 | 50 | -9 |
| qv10 | 1 | 83 | 74 | -9 | 52 | 50 | -2 |
| qv10 | 42 | 81 | 83 | 2 | 50 | 51 | 1 |
| random10x60 | 0 | 292 | 265 | -27 | 284 | 262 | -22 |
| random10x60 | 1 | 309 | 299 | -10 | 301 | 285 | -16 |
| random10x60 | 42 | 272 | 291 | 19 | 278 | 277 | -1 |
| ring10 | 0 | 91 | 90 | -1 | 84 | 85 | 1 |
| ring10 | 1 | 91 | 88 | -3 | 85 | 83 | -2 |
| ring10 | 42 | 90 | 89 | -1 | 81 | 85 | 4 |

## Self-checks
| check | fixture | heuristic | seed | passed | error |
|---|---|---|---|---|---|
| ignoring_final_layout_must_fail | qft10 | decay | 0 | True |  |
| extra_x_gate_must_fail | qft10 | decay | 0 | True |  |

## Limitations
- Six circuits, 10 qubits, one bidirectional line, trivial initial layout, `SabreSwap` only (no `SabreLayout`, no full `transpile`).
- One build: this compares the heuristic on and off on the same revision; it does not compare against the pre-feature revision.
- D2 and N2 expand SWAPs only; other two-qubit operations (including unitary gates) remain one operation each. These are not metrics after full native-basis translation.
- D2/N2, swap and depth columns are routing-quality observations, not timings.
