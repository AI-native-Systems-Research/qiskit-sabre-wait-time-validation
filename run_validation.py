#!/usr/bin/env python
"""Check wait-time SABRE against the original unitary on 16 ten-qubit circuits."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

os.environ["QISKIT_PARALLEL"] = "FALSE"
SEEDS = [0, 1, 42, 2, 7, 123]
CHECKS = ("ignoring_final_layout_must_fail", "extra_x_gate_must_fail")


def fixtures():
    import numpy as np
    from qiskit import QuantumCircuit, QuantumRegister
    from qiskit.quantum_info import random_unitary
    from test.benchmarks import qft, random_circuit_hex, utils

    def quantum_volume(seed):
        rng = np.random.default_rng(seed)
        qc = QuantumCircuit(10)
        for _ in range(10):
            perm = rng.permutation(10)
            for k in range(0, 10, 2):
                qc.append(random_unitary(4, seed=rng), [int(perm[k]), int(perm[k + 1])])
        return qc

    random = partial(utils.random_circuit, 10, max_operands=2,
                     measure=False, conditional=False, reset=False)
    return {
        "qft10": lambda: qft.build_model_circuit(QuantumRegister(10)),
        "random10x60": partial(random, 60, seed=42),
        "adder4": partial(utils.build_ripple_adder_circuit, 4),
        "ring10": lambda: random_circuit_hex.make_circuit_ring(10, 20, 0)[0],
        "qv10": partial(quantum_volume, 42),
        "dtc10": partial(utils.dtc_unitary, 10),
        "random10x20": partial(random, 20, seed=7),
        "random10x40": partial(random, 40, seed=123),
        "qv10_seed7": partial(quantum_volume, 7),
        "bv10": partial(utils.bv_all_ones, 10),
        "bvlike10": partial(utils.trivial_bvlike_circuit, 10),
        "trotter10": partial(utils.trotter_circuit, 10, reps=2),
        "qaoa10": partial(utils.qaoa_circuit, 10, reps=2),
        "grover10": partial(utils.grover_circuit, 10),
        "mcx10": partial(utils.mcx_circuit, 10),
        "modular_adder10": partial(utils.modular_adder_circuit, 10),
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def route_and_check(qc, reference, cmap, seed):
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import PassManager
    from qiskit.transpiler.passes import ApplyLayout, SabreSwap, TrivialLayout

    out = PassManager([TrivialLayout(cmap), ApplyLayout(),
                       SabreSwap(cmap, heuristic="wait_time", seed=seed, trials=1)]).run(qc.copy())
    require(out.num_qubits == 10, "Output width changed")
    require(out.layout is not None and out.layout.initial_layout is not None
            and out.layout.final_layout is not None, "Missing layout metadata")
    edges = set(map(tuple, cmap.get_edges()))
    for inst in out.data:
        if inst.operation._directive:
            continue
        qubits = tuple(out.find_bit(q).index for q in inst.qubits)
        require(len(qubits) <= 2 and (len(qubits) != 2 or qubits in edges),
                f"Unrouted gate: {inst.operation.name}{qubits}")
    require(Operator.from_circuit(out) == reference, "Operator mismatch")
    return out


def self_checks(sample):
    from qiskit.quantum_info import Operator

    results = []
    for name in CHECKS:
        rec = {"record": "self_check", "name": name, "passed": False}
        try:
            require(sample is not None, "No passing case with a changed final permutation")
            out, reference, fixture, seed = sample
            rec.update(fixture=fixture, seed=seed)
            wrong = out.copy()
            ignore_layout = name == CHECKS[0]
            if not ignore_layout:
                wrong.x(0)
            require(Operator.from_circuit(wrong, ignore_set_layout=ignore_layout) != reference,
                    "Deliberate error was not detected")
            rec["passed"] = True
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # Includes Python-visible Rust panics.
            rec["error"] = repr(exc)
        results.append(rec)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qiskit-src", type=Path, default=Path(__file__).parent / "qiskit-src")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    parser.add_argument("--out", type=Path, default=Path("results/results.jsonl"))
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds) or any(s < 0 or s >= 2**64 for s in args.seeds):
        parser.error("Seeds must be distinct unsigned 64-bit integers")
    source = args.qiskit_src.resolve()
    sys.path.insert(0, str(source))
    import qiskit
    import qiskit._accelerate
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import CouplingMap, PassManager
    from qiskit.transpiler.passes import Unroll3qOrMore

    for module in (qiskit, qiskit._accelerate):
        require(Path(module.__file__).resolve().is_relative_to(source), "Wrong Qiskit source")
    revision = source / "REVISION"
    sha = (revision.read_text().strip() if revision.exists() else
           subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip())
    builders = fixtures()
    records = [dict(record="environment", sha=sha, qiskit_version=qiskit.__version__,
                    accelerate_file=qiskit._accelerate.__file__, python=sys.version.split()[0],
                    timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    fixtures=list(builders), seeds=args.seeds, heuristic="wait_time",
                    coupling_map="line(10)", trials=1)]
    cmap, sample = CouplingMap.from_line(10), None
    for name, builder in builders.items():
        error = None
        print(f"Preparing {name}", flush=True)
        try:
            qc = builder().remove_final_measurements(inplace=False)
            qc = qc.assign_parameters([0.1 * (i + 1) for i in range(qc.num_parameters)])
            qc = PassManager([Unroll3qOrMore()]).run(qc)
            require(qc.num_qubits == 10 and all(len(i.qubits) <= 2 for i in qc.data),
                    "Expected 10 qubits and only one- or two-qubit instructions")
            reference = Operator.from_circuit(qc)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            error = f"Preparation failed: {exc!r}"
        for seed in args.seeds:
            print(f"  seed {seed}: ", end="", flush=True)
            rec = dict(record="case", fixture=name, seed=seed, passed=False)
            try:
                require(error is None, error)
                out = route_and_check(qc, reference, cmap, seed)
                final = out.layout.final_index_layout()
                rec.update(passed=True, final_permutation=final)
                if sample is None and final != list(range(10)):
                    sample = (out, reference, name, seed)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as exc:
                rec["error"] = repr(exc)
            records.append(rec)
            print("PASS" if rec["passed"] else f"FAIL {rec['error']}", flush=True)
    records += self_checks(sample)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    failed = sum(not r["passed"] for r in records[1:])
    print(f"{failed} failures; wrote {args.out}")
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main())
