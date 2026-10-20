# SABRE wait-time correctness

Run 16 deterministic ten-qubit circuits with `wait_time`, using routing seeds
`0 1 42 2 7 123`: **96 cases**, plus two negative self-checks.
Each routed output must match the original circuit's unitary, including global
phase with Qiskit's default tolerances, and preserve width, layout metadata,
and connectivity on a bidirectional line. Routing uses a trivial layout and one trial.

## Run using the existing release build

From this repository:

```bash
../qiskit-evolved/.venv/bin/python run_validation.py --qiskit-src ../qiskit-evolved
../qiskit-evolved/.venv/bin/python make_report.py
```

Results go to `results/results.jsonl`; the short summary goes to `report.md`.
Both scripts return nonzero on failure. The reporter also rejects incomplete
or duplicate results. Exceptions, including Python-visible Rust panics, are failures.

## Self-checks

The two self-checks are negative controls: they show the unitary comparison is
strong enough to fail. Both start from the first passing case whose final
permutation is not the identity (with an identity permutation, ignoring the
layout would change nothing and the first check would be meaningless), break
it on purpose, and pass only if the broken circuit no longer matches the reference:

- **Ignored layout** (`ignoring_final_layout_must_fail`): build the operator with
  `ignore_set_layout=True`, so the qubit permutation from routing SWAPs is not
  undone. This confirms the layout metadata matters to the comparison.
- **Extra X gate** (`extra_x_gate_must_fail`): append an X gate on physical
  qubit 0 while still using the layout. This confirms a small gate-level
  change is caught.

If either broken circuit still matched, the checker would be too weak to trust,
so the run fails.

## Circuits

The original six are QFT, a random circuit of depth 60, a four-bit ripple adder,
a ring circuit, quantum volume, and DTC evolution.
The ten additions are random circuits of depths 20 and 40, another quantum-volume
circuit, Bernstein–Vazirani and BV-like circuits, Trotter evolution, QAOA,
Grover, multi-controlled X, and modular addition.

All builders come from `qiskit-evolved/test/benchmarks`, except the small
quantum-volume builder, which uses one seeded generator for both pairings and
unitaries. Fixture seeds are fixed in `fixtures()` and are independent of routing
seeds. Trotter and QAOA use two repetitions; QAOA parameters are bound to
`0.1, 0.2, …` in Qiskit's parameter order. Final measurements are removed and
instructions on three or more qubits are expanded before building the reference.

## Fresh release build

Requires Python 3.10+ and the Qiskit build toolchain:

```bash
mkdir -p qiskit-src
git -C ../qiskit-evolved archive HEAD | tar -x -C qiskit-src
git -C ../qiskit-evolved rev-parse HEAD > qiskit-src/REVISION
~/.pyenv/versions/3.11.8/bin/python -m venv .venv
(cd qiskit-src && QISKIT_BUILD_PROFILE=release ../.venv/bin/pip install -e .)
.venv/bin/pip install 'ddt>=1.2.0'
.venv/bin/python run_validation.py && .venv/bin/python make_report.py
```

`ddt` is needed for the benchmark imports. `--qiskit-src` defaults to the
`qiskit-src` directory beside the runner. Override routing seeds with `--seeds`;
override output paths with `--out` and the reporter's input with `--results`.
The runner enforces `QISKIT_PARALLEL=FALSE`.

The recorded run uses revision `319fa5fa703bc924008db812f5ddfec6b56c38f7`, built
from `qiskit-evolved` with
`QISKIT_BUILD_PROFILE=release .venv/bin/python setup.py build_rust --inplace --release`.
The loaded extension matches the local release artifact (SHA-256
`b019b47bb19dc956747134a85e33e467136614b7c2749ef54696ed4c4df6a5ff`).
Commit results and report together. These are routing checks for the selected
circuits and seeds, not a general correctness proof.
