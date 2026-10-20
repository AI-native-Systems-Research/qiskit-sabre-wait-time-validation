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
    """Return the 16 named test circuits as zero-argument builder callables.

    The builders are lazy so that ``main`` can build each circuit inside its own
    ``try`` block: a fixture that fails to build is recorded as failing for every
    seed instead of aborting the whole run. Every builder is deterministic (fixed
    seeds), and every circuit must end up with exactly 10 qubits.
    """
    # Imported here, not at module level, because these must come from the Qiskit
    # source tree that main() has just put at the front of sys.path.
    # NumPy provides the seeded random generator for the quantum-volume builder.
    import numpy as np
    # Circuit classes used by the local quantum-volume builder and by the QFT fixture.
    from qiskit import QuantumCircuit, QuantumRegister
    # Haar-random unitaries for the two-qubit blocks of the quantum-volume circuit.
    from qiskit.quantum_info import random_unitary
    # Circuit builders from Qiskit's own benchmark suite (needs `ddt` installed).
    from test.benchmarks import qft, random_circuit_hex, utils

    def quantum_volume(seed):
        """Build a 10-qubit, 10-layer quantum-volume circuit from one seeded generator."""
        # One generator drives both the qubit pairings and the unitaries, so the
        # whole circuit is fixed by `seed`.
        rng = np.random.default_rng(seed)
        # Start from an empty 10-qubit circuit with no classical bits.
        qc = QuantumCircuit(10)
        # Quantum volume uses depth equal to width: 10 layers for 10 qubits.
        for _ in range(10):
            # Shuffle the qubits; consecutive entries form this layer's pairs.
            perm = rng.permutation(10)
            # Step through the permutation two at a time: 5 disjoint pairs per layer.
            for k in range(0, 10, 2):
                # Apply a random 4x4 (two-qubit) unitary to the pair; int() turns the
                # NumPy integers into plain qubit indices.
                qc.append(random_unitary(4, seed=rng), [int(perm[k]), int(perm[k + 1])])
        # Every layer touches all 10 qubits, so the result is fully two-qubit-entangled.
        return qc

    # Shared random-circuit builder: 10 qubits, gates on at most two qubits, and no
    # measurements, classically conditioned gates or resets, so the result is a
    # pure unitary. Callers still supply the depth (positionally) and the seed.
    random = partial(utils.random_circuit, 10, max_operands=2,
                     measure=False, conditional=False, reset=False)
    # Fixture name -> builder. Insertion order is the order cases run and are reported.
    return {
        # Quantum Fourier transform on a 10-qubit register: H gates plus all-to-all
        # controlled-phase gates, which forces many SWAPs on a line.
        "qft10": lambda: qft.build_model_circuit(QuantumRegister(10)),
        # Random circuit of depth 60 with circuit seed 42.
        "random10x60": partial(random, 60, seed=42),
        # 4-bit ripple-carry adder: registers a(4) + b(4) + cin(1) + cout(1) = 10 qubits.
        # It contains Toffoli gates (expanded later) and final measurements (removed later).
        "adder4": partial(utils.build_ripple_adder_circuit, 4),
        # Ring circuit: 10 qubits, depth 20, seed 0. The builder returns
        # [circuit, circuit_with_measurements, num_qubits]; [0] takes the unmeasured one.
        "ring10": lambda: random_circuit_hex.make_circuit_ring(10, 20, 0)[0],
        # Quantum-volume circuit from the local builder above, seed 42.
        "qv10": partial(quantum_volume, 42),
        # Floquet unitary for discrete-time-crystal (DTC) evolution, using the
        # builder's default parameters (g=0.95, seed=12345).
        "dtc10": partial(utils.dtc_unitary, 10),
        # Shallower random circuit: depth 20, circuit seed 7.
        "random10x20": partial(random, 20, seed=7),
        # Medium random circuit: depth 40, circuit seed 123.
        "random10x40": partial(random, 40, seed=123),
        # Second quantum-volume instance with a different seed (7).
        "qv10_seed7": partial(quantum_volume, 7),
        # Bernstein-Vazirani for the all-ones secret: every data qubit has a CX
        # onto the last qubit (star-shaped interactions).
        "bv10": partial(utils.bv_all_ones, 10),
        # BV-like circuit: CX from every qubit onto the last one, then X and Z gates.
        "bvlike10": partial(utils.trivial_bvlike_circuit, 10),
        # Trotterized evolution of a nearest-neighbour XX+YY+ZZ chain with a Z
        # field, two Trotter steps.
        "trotter10": partial(utils.trotter_circuit, 10, reps=2),
        # QAOA ansatz with seeded random ZZ weights, two repetitions. It has free
        # parameters, which main() binds to fixed values.
        "qaoa10": partial(utils.qaoa_circuit, 10, reps=2),
        # Grover search: 9 state qubits plus 1 target qubit.
        "grover10": partial(utils.grover_circuit, 10),
        # Multi-controlled X: 8 controls, 1 target and 1 clean ancilla.
        "mcx10": partial(utils.mcx_circuit, 10),
        # Modular adder on two 5-qubit registers (10 qubits in total).
        "modular_adder10": partial(utils.modular_adder_circuit, 10),
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def route_and_check(qc, reference, cmap, seed):
    """Route ``qc`` with wait-time SABRE and check that the result is correct.

    Raises ``ValueError`` if any check fails; otherwise returns the routed circuit.
    The checks are: the width is unchanged, layout metadata is present, every
    two-qubit gate sits on a coupling-map edge, and the routed circuit's unitary
    (with its layout undone) equals ``reference``.
    """
    # Imported lazily so the Qiskit from --qiskit-src is used (see main()).
    # Operator turns a circuit into its full unitary matrix.
    from qiskit.quantum_info import Operator
    # PassManager runs a list of transpiler passes in order.
    from qiskit.transpiler import PassManager
    # The three passes that make up this layout-plus-routing pipeline.
    from qiskit.transpiler.passes import ApplyLayout, SabreSwap, TrivialLayout

    # TrivialLayout maps virtual qubit i to physical qubit i. ApplyLayout rewrites
    # the circuit onto physical qubits and records that initial layout.
    # SabreSwap inserts SWAPs so every two-qubit gate is on an edge, using the
    # wait-time heuristic under test, this routing seed and a single trial, so
    # each run is deterministic. It also records the final qubit permutation.
    # qc.copy() keeps the shared prepared circuit unchanged across seeds.
    out = PassManager([TrivialLayout(cmap), ApplyLayout(),
                       SabreSwap(cmap, heuristic="wait_time", seed=seed, trials=1)]).run(qc.copy())
    # The line has exactly 10 physical qubits and the input has 10, so no
    # ancillas should be added and no qubits dropped.
    require(out.num_qubits == 10, "Output width changed")
    # The TranspileLayout and both of its layouts must exist. Without them the
    # operator check below could not undo the routing permutation and would
    # compare the wrong thing.
    require(out.layout is not None and out.layout.initial_layout is not None
            and out.layout.final_layout is not None, "Missing layout metadata")
    # Set of allowed (control, target) physical pairs. from_line() is bidirectional,
    # so both (i, i+1) and (i+1, i) are present and gate direction does not matter.
    edges = set(map(tuple, cmap.get_edges()))
    # Check connectivity instruction by instruction.
    for inst in out.data:
        # Skip directives such as barriers: they are not physical operations
        # and may legitimately span non-adjacent qubits.
        if inst.operation._directive:
            continue
        # Physical qubit indices this instruction acts on in the routed circuit.
        qubits = tuple(out.find_bit(q).index for q in inst.qubits)
        # The gate must act on at most two qubits, and a two-qubit gate must act on
        # a coupled pair, in the order it appears in `edges`.
        require(len(qubits) <= 2 and (len(qubits) != 2 or qubits in edges),
                f"Unrouted gate: {inst.operation.name}{qubits}")
    # Operator.from_circuit uses out.layout to undo the initial layout and the
    # final SWAP permutation, giving the unitary in the original qubit order.
    # Operator equality uses np.allclose with default tolerances and no phase
    # fixing, so the global phase must match too.
    require(Operator.from_circuit(out) == reference, "Operator mismatch")
    # Hand the routed circuit back so the caller can record its final permutation.
    return out


def self_checks(sample):
    """Mutate a known-good routed circuit and confirm the checker catches each error.

    ``sample`` is ``(routed_circuit, reference_operator, fixture_name, seed)`` from a
    passing case whose final permutation is not the identity, or ``None`` if there
    was no such case. Returns one ``self_check`` record per entry in ``CHECKS``. A
    record passes only if the deliberately broken circuit no longer matches the
    reference, which shows the operator comparison can actually fail.
    """
    # Imported lazily so the Qiskit from --qiskit-src is used (see main()).
    from qiskit.quantum_info import Operator

    # One record per self-check, in CHECKS order.
    results = []
    # CHECKS[0] ignores the layout metadata; CHECKS[1] adds an extra X gate.
    for name in CHECKS:
        # Start as failed; set to passed only once the mutation is detected.
        rec = {"record": "self_check", "name": name, "passed": False}
        try:
            # A non-identity final permutation is required. With a trivial initial
            # layout and an identity final layout, ignoring the layout changes
            # nothing, so the first check would pass for no reason.
            require(sample is not None, "No passing case with a changed final permutation")
            # Unpack the routed circuit, its reference unitary, and where it came from.
            out, reference, fixture, seed = sample
            # Record which case was mutated, for traceability in the results file.
            rec.update(fixture=fixture, seed=seed)
            # Work on a copy so each check starts from the unmodified routed circuit.
            wrong = out.copy()
            # True for the "ignore final layout" check, False for the "extra X" check.
            ignore_layout = name == CHECKS[0]
            # The "extra X" check appends an X gate on physical qubit 0. That changes
            # the unitary, while the layout metadata is still used.
            if not ignore_layout:
                wrong.x(0)
            # Build the unitary from the broken circuit. For the first check,
            # ignore_set_layout=True skips undoing the SWAP permutation; for the
            # second, the layout is used but the extra X is there. Either way it
            # must differ from the reference, or the checker is too weak.
            require(Operator.from_circuit(wrong, ignore_set_layout=ignore_layout) != reference,
                    "Deliberate error was not detected")
            # The deliberate error was caught, so the self-check passes.
            rec["passed"] = True
        # Let Ctrl-C and sys.exit() stop the run instead of becoming a failed record.
        except (KeyboardInterrupt, SystemExit):
            raise
        # Record any other error, including PyO3's PanicException, which derives
        # from BaseException rather than Exception.
        except BaseException as exc:  # Includes Python-visible Rust panics.
            rec["error"] = repr(exc)
        # Keep the record whether it passed or failed.
        results.append(rec)
    # main() appends these after the per-case records.
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

    # Confirm that both the pure-Python package and the compiled Rust extension
    # were loaded from --qiskit-src and not from another installed Qiskit. If they
    # were not, the run would validate the wrong code.
    for module in (qiskit, qiskit._accelerate):
        require(Path(module.__file__).resolve().is_relative_to(source), "Wrong Qiskit source")
    # A tree exported with `git archive` has no .git directory, so its commit SHA
    # is written to a REVISION file at export time (see README).
    revision = source / "REVISION"
    # Use REVISION if present; otherwise ask git for the checkout's HEAD commit.
    sha = (revision.read_text().strip() if revision.exists() else
           subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip())
    # Fixture name -> builder. Called only now, after sys.path points at the source tree.
    builders = fixtures()
    # The first record holds provenance: exact Qiskit commit and version, which
    # compiled extension was loaded, Python version, UTC run time, and the
    # parameters of this run (fixtures, seeds, heuristic, coupling map, trials).
    records = [dict(record="environment", sha=sha, qiskit_version=qiskit.__version__,
                    accelerate_file=qiskit._accelerate.__file__, python=sys.version.split()[0],
                    timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    fixtures=list(builders), seeds=args.seeds, heuristic="wait_time",
                    coupling_map="line(10)", trials=1)]
    # Bidirectional 10-qubit line 0-1-...-9, the hardest connectivity for routing.
    # `sample` will hold the first passing case with a non-identity final
    # permutation, for use by self_checks().
    cmap, sample = CouplingMap.from_line(10), None
    # Each fixture is prepared once and then routed with every seed.
    for name, builder in builders.items():
        # Preparation error message for this fixture, if any.
        error = None
        # Progress output; flush so it shows immediately even when piped.
        print(f"Preparing {name}", flush=True)
        try:
            # Build the circuit and drop its final measurements (and any classical
            # registers that become unused), leaving a pure unitary. inplace=False
            # returns a new circuit.
            qc = builder().remove_final_measurements(inplace=False)
            # Bind free parameters (only QAOA has any) to 0.1, 0.2, ... in Qiskit's
            # parameter order. For a circuit without parameters this binds nothing.
            qc = qc.assign_parameters([0.1 * (i + 1) for i in range(qc.num_parameters)])
            # Expand instructions on three or more qubits (Toffolis, MCX, etc.) into
            # one- and two-qubit gates, so routing on a line is possible and the
            # connectivity check means something.
            qc = PassManager([Unroll3qOrMore()]).run(qc)
            # Sanity-check the prepared input: exactly 10 qubits (to match the line)
            # and nothing wider than two qubits.
            require(qc.num_qubits == 10 and all(len(i.qubits) <= 2 for i in qc.data),
                    "Expected 10 qubits and only one- or two-qubit instructions")
            # Reference unitary (1024x1024) of the unrouted circuit. Every routed
            # output for this fixture is compared against it.
            reference = Operator.from_circuit(qc)
        # Let Ctrl-C and sys.exit() stop the run.
        except (KeyboardInterrupt, SystemExit):
            raise
        # Any other preparation error is kept. It is reported as a failure for each
        # seed below instead of crashing the run.
        except BaseException as exc:
            error = f"Preparation failed: {exc!r}"
        # Route the same prepared circuit once per routing seed.
        for seed in args.seeds:
            # Print the case label; PASS/FAIL is added to the same line below.
            print(f"  seed {seed}: ", end="", flush=True)
            # Case record, failed by default until every check passes.
            rec = dict(record="case", fixture=name, seed=seed, passed=False)
            try:
                # If preparation failed, raise its message so this case records it.
                require(error is None, error)
                # Route with wait-time SABRE and run all correctness checks; raises on failure.
                out = route_and_check(qc, reference, cmap, seed)
                # Entry i is the physical qubit holding original qubit i at the end.
                # It is the identity only if the SWAPs cancel out overall.
                final = out.layout.final_index_layout()
                # All checks passed: mark the case and keep the permutation for the report.
                rec.update(passed=True, final_permutation=final)
                # Keep the first passing case whose SWAPs left a real permutation; the
                # "ignore final layout" self-check needs one to be meaningful.
                if sample is None and final != list(range(10)):
                    sample = (out, reference, name, seed)
            # Let Ctrl-C and sys.exit() stop the run.
            except (KeyboardInterrupt, SystemExit):
                raise
            # Record any failed check or crash, including Rust panics.
            except BaseException as exc:
                rec["error"] = repr(exc)
            # Keep the record whether it passed or failed.
            records.append(rec)
            # Finish the progress line with the outcome.
            print("PASS" if rec["passed"] else f"FAIL {rec['error']}", flush=True)
    # Add the two negative self-checks, which show the checker can detect errors.
    records += self_checks(sample)
    # Create the output directory (results/ by default) if it does not exist.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Write JSON Lines: one record per line, read later by make_report.py.
    args.out.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    # Count failed cases and self-checks. records[1:] skips the environment
    # record, which has no "passed" field.
    failed = sum(not r["passed"] for r in records[1:])
    # One-line summary for the console.
    print(f"{failed} failures; wrote {args.out}")
    # Exit status: 0 if everything passed, 1 if anything failed.
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main())
