# SABRE wait-time validation

Six deterministic 10-qubit benchmark circuits, three routing seeds (`0 1 42`),
and the `decay` and `wait_time` heuristics give 36 correctness cases on one
bidirectional line. Routing uses a trivial initial layout and `trials=1`.
Every case must preserve the exact operator (including global phase, with
Qiskit's default tolerances), width, layout metadata, and connectivity.
Two negative self-checks must detect ignored layout metadata and an extra X gate.

The report compares two-qubit depth (D2) and gate count (N2) after decomposing
every SWAP into three CX gates. Differences are **on − off**; negative is an
improvement. Quality differences are informational and do not affect correctness.
Other gates are not translated or optimized. See `report.md` for the limitations
and `results/results.jsonl` for the complete records.

## Setup

Run from this independent repository beside `qiskit-evolved`. Exporting `HEAD`
excludes uncommitted edits and keeps build products out of the source checkout.

```bash
mkdir -p qiskit-src results
git -C ../qiskit-evolved archive HEAD | tar -x -C qiskit-src
git -C ../qiskit-evolved rev-parse HEAD > qiskit-src/REVISION
~/.pyenv/versions/3.11.8/bin/python -m venv .venv
(cd qiskit-src && QISKIT_BUILD_PROFILE=release ../.venv/bin/pip install -e .)
.venv/bin/pip install 'ddt>=1.2.0'
.venv/bin/python -c "import qiskit, qiskit._accelerate; print(qiskit.__version__, qiskit._accelerate.__file__)"
```

The extension path must be under this repository's `qiskit-src/`.
`QISKIT_BUILD_PROFILE=release` is required because editable builds otherwise
default to debug. `ddt` is needed to import the checkout's benchmark package.
Re-export and rebuild when the source revision changes.

## Run

```bash
.venv/bin/python run_validation.py && .venv/bin/python make_report.py
```

Equivalently, with the virtual environment activated:

```bash
python run_validation.py && python make_report.py
```

Defaults: `--qiskit-src ./qiskit-src` (relative to the runner),
`--seeds 0 1 42`, `--out results/results.jsonl`.
Report defaults: `--results results/results.jsonl --out report.md`.
Output paths are relative to the working directory. The runner requires Python
3.10 or newer and enforces `QISKIT_PARALLEL=FALSE`.

Each script exits zero only for a passing run. The report checks completeness
and rejects duplicate/missing cases or obsolete results without decomposed
D2/N2 metrics. To inspect a failed run, invoke `make_report.py` separately; its
report will say FAIL and it will return nonzero. Routing, preparation, and
self-check exceptions (including Python-visible Rust panics) are failures.

## Existing release build

The checked-in results use the plan's existing-build option, with source
revision `72efe50ac12bd949970456cd59c46eaa812b3a72`:

```bash
../qiskit-evolved/.venv/bin/python run_validation.py --qiskit-src ../qiskit-evolved
../qiskit-evolved/.venv/bin/python make_report.py
```

The loaded extension was byte-identical to
`qiskit-evolved/target/release/libqiskit_pyext.dylib` (SHA-256
`b019b47bb19dc956747134a85e33e467136614b7c2749ef54696ed4c4df6a5ff`).
The runtime source matched `HEAD`; existing uncommitted changes were confined
to design documents, `.gitignore`, and a Python test module outside these
fixtures. The JSONL environment record identifies the actual source and
extension paths. No build products were added to the feature checkout.

Commit `results/results.jsonl` and `report.md` together after a successful run.
This repository and its evidence are independent of the Qiskit feature PR.
