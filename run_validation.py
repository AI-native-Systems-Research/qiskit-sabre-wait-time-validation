#!/usr/bin/env python
"""Route six 10-qubit benchmark circuits with SABRE, with and without the wait-time
heuristic, and check that every routed circuit implements the same unitary."""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ["QISKIT_PARALLEL"] = "FALSE"
N = 10
HEURISTICS = ("decay", "wait_time")


def build_fixtures():
    """Return lazy builders so one broken fixture does not skip the others."""
    import numpy as np
    from qiskit import QuantumCircuit, QuantumRegister
    from qiskit.quantum_info import random_unitary
    from test.benchmarks.qft import build_model_circuit
    from test.benchmarks.random_circuit_hex import make_circuit_ring
    from test.benchmarks.utils import build_ripple_adder_circuit, dtc_unitary, random_circuit

    def qv(width, depth, seed):  # build_qv_model_circuit with one seeded generator
        rng = np.random.default_rng(seed)
        qc = QuantumCircuit(width)
        for _ in range(depth):
            perm = rng.permutation(width)
            for k in range(width // 2):
                qc.append(random_unitary(4, seed=rng), [int(perm[2 * k]), int(perm[2 * k + 1])])
        return qc

    return {
        "qft10": lambda: build_model_circuit(QuantumRegister(N)),
        "random10x60": lambda: random_circuit(
            N, 60, max_operands=2, measure=False, conditional=False, reset=False, seed=42
        ),
        "adder4": lambda: build_ripple_adder_circuit(4),
        "ring10": lambda: make_circuit_ring(N, 2 * N, 0)[0],
        "qv10": lambda: qv(N, N, 42),
        "dtc10": lambda: dtc_unitary(N),
    }


def environment(qiskit_src, seeds):
    import qiskit
    import qiskit._accelerate

    source = Path(qiskit_src).resolve()
    for module in (qiskit, qiskit._accelerate):
        if not Path(module.__file__).resolve().is_relative_to(source):
            raise RuntimeError(
                f"{module.__name__} was imported outside {source}: {module.__file__}"
            )
    rev = os.path.join(qiskit_src, "REVISION")
    if os.path.exists(rev):
        sha = Path(rev).read_text(encoding="utf-8").strip()
    else:
        try:
            sha = subprocess.check_output(
                ["git", "-C", qiskit_src, "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            sha = "unknown"
    return {
        "record": "environment",
        "sha": sha,
        "qiskit_src": os.path.abspath(qiskit_src),
        "qiskit_file": qiskit.__file__,
        "accelerate_file": qiskit._accelerate.__file__,
        "qiskit_version": qiskit.__version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "seeds": seeds,
        "coupling_map": f"line({N})",
        "heuristics": HEURISTICS,
        "trials": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def check_case(name, qc, ref, cmap, edges, heuristic, seed):
    from qiskit.circuit.library import SwapGate
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import PassManager
    from qiskit.transpiler.passes import ApplyLayout, SabreSwap, TrivialLayout

    t0 = time.perf_counter()
    pm = PassManager(
        [
            TrivialLayout(cmap),
            ApplyLayout(),
            SabreSwap(cmap, heuristic=heuristic, seed=seed, trials=1),
        ]
    )
    out = pm.run(qc.copy())
    violations = 0
    for inst in out.data:
        if inst.operation._directive:
            continue
        phys = tuple(out.find_bit(q).index for q in inst.qubits)
        if len(phys) > 2 or (len(phys) == 2 and phys not in edges):
            violations += 1
    layout_present = (
        out.layout is not None
        and out.layout.initial_layout is not None
        and out.layout.final_layout is not None
    )
    final = out.layout.final_index_layout() if layout_present else None
    decomposed = out.decompose(gates_to_decompose=SwapGate)
    is_2q_gate = lambda inst: len(inst.qubits) == 2 and not inst.operation._directive
    rec = {
        "record": "case",
        "fixture": name,
        "heuristic": heuristic,
        "seed": seed,
        "width_ok": out.num_qubits == qc.num_qubits,
        "layout_present": layout_present,
        "final_permutation": final,
        "final_permutation_changed": final is not None and final != list(range(N)),
        "swaps_inserted": out.count_ops().get("swap", 0) - qc.count_ops().get("swap", 0),
        "output_ops": out.size(),
        "output_depth": out.depth(),
        "d2_after_swap_decomposition": decomposed.depth(is_2q_gate),
        "n2_after_swap_decomposition": sum(is_2q_gate(inst) for inst in decomposed.data),
        "connectivity_violations": violations,
        "operator_equal": Operator.from_circuit(out) == ref,
    }
    rec["passed"] = (
        rec["operator_equal"] and violations == 0 and rec["width_ok"] and rec["layout_present"]
    )
    rec["seconds"] = round(time.perf_counter() - t0, 2)
    return rec, out


def self_checks(out, ref):
    """Prove the comparison can fail: run on a passed case whose final permutation changed."""
    from qiskit.quantum_info import Operator

    records = []
    for name in ("ignoring_final_layout_must_fail", "extra_x_gate_must_fail"):
        rec = {"record": "self_check", "name": name, "passed": False}
        try:
            if out is None:
                raise RuntimeError("no_case_with_changed_final_permutation")
            if name == "ignoring_final_layout_must_fail":
                rec["passed"] = Operator.from_circuit(out, ignore_set_layout=True) != ref
            else:
                wrong = out.copy()  # copy() keeps the layout metadata
                wrong.x(0)
                rec["passed"] = Operator.from_circuit(wrong) != ref
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # PyO3 PanicException is not an Exception
            rec["error"] = repr(exc)
        records.append(rec)
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--qiskit-src",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "qiskit-src"),
    )
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 42])
    p.add_argument("--out", default="results/results.jsonl")
    args = p.parse_args()
    if len(set(args.seeds)) != len(args.seeds) or any(s < 0 or s >= 2**64 for s in args.seeds):
        p.error("--seeds must be distinct unsigned 64-bit integers")
    sys.path.insert(0, os.path.abspath(args.qiskit_src))  # test.benchmarks comes from the checkout
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import CouplingMap, PassManager
    from qiskit.transpiler.passes import Unroll3qOrMore

    cmap = CouplingMap.from_line(N)
    edges = set(map(tuple, cmap.get_edges()))
    records = [environment(args.qiskit_src, args.seeds)]
    sample = None
    for name, builder in build_fixtures().items():
        preparation_error = None
        try:
            qc = PassManager([Unroll3qOrMore()]).run(
                builder().remove_final_measurements(inplace=False)
            )
            if qc.num_qubits != N or any(len(i.qubits) > 2 for i in qc.data):
                raise ValueError(f"{name}: expected {N} qubits and only 1-/2-qubit instructions")
            ref = Operator.from_circuit(qc)
            records.append(
                {
                    "record": "fixture",
                    "fixture": name,
                    "input_ops": qc.size(),
                    "input_depth": qc.depth(),
                    "input_swaps": qc.count_ops().get("swap", 0),
                }
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            preparation_error = f"Fixture preparation: {exc!r}"
            records.append({"record": "fixture", "fixture": name, "error": preparation_error})
        for seed in args.seeds:
            for heuristic in HEURISTICS:
                print(f"Running {name} seed {seed} {heuristic}", flush=True)
                try:
                    if preparation_error is not None:
                        raise RuntimeError(preparation_error)
                    rec, out = check_case(name, qc, ref, cmap, edges, heuristic, seed)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException as exc:  # PyO3 PanicException is not an Exception
                    rec, out = {
                        "record": "case",
                        "fixture": name,
                        "heuristic": heuristic,
                        "seed": seed,
                        "passed": False,
                        "error": repr(exc),
                    }, None
                records.append(rec)
                print(
                    f"{name:12s} seed {seed:2d} {heuristic:9s} swaps {rec.get('swaps_inserted', '?'):>4}"
                    f" D2 {rec.get('d2_after_swap_decomposition', '?'):>4}"
                    f" N2 {rec.get('n2_after_swap_decomposition', '?'):>4}"
                    f" {'PASS' if rec['passed'] else 'FAIL'}",
                    flush=True,
                )
                if sample is None and rec["passed"] and rec.get("final_permutation_changed"):
                    sample = (out, ref, name, seed, heuristic)
    checks = self_checks(*sample[:2]) if sample else self_checks(None, None)
    for rec in checks:
        if sample:
            rec.update(fixture=sample[2], seed=sample[3], heuristic=sample[4])
        print(f"{rec['name']}: {'PASS' if rec['passed'] else 'FAIL'}", flush=True)
    records += checks
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    failed = [r for r in records if r["record"] in ("case", "self_check") and not r["passed"]]
    print(f"{len(failed)} failed; wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
