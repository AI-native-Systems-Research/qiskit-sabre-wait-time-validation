#!/usr/bin/env python
"""Check result completeness and write report.md; no routing, no Qiskit."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results/results.jsonl")
    p.add_argument("--out", default="report.md")
    a = p.parse_args()
    by = defaultdict(list)
    try:
        with open(a.results, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    if not isinstance(r, dict) or r.get("record") not in (
                        "environment",
                        "fixture",
                        "case",
                        "self_check",
                    ):
                        p.error("Every result must be a recognized JSON record.")
                    by[r["record"]].append(r)
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    if not by["environment"]:
        p.error("Missing environment record.")
    env, cases, checks = by["environment"][0], by["case"], by["self_check"]
    required_env = (
        "sha",
        "accelerate_file",
        "qiskit_version",
        "python",
        "platform",
        "timestamp",
        "seeds",
        "coupling_map",
        "trials",
        "heuristics",
    )
    if any(k not in env for k in required_env):
        p.error("Incomplete environment record.")
    if (
        not isinstance(env["seeds"], list)
        or any(type(s) is not int or s < 0 or s >= 2**64 for s in env["seeds"])
        or len(set(env["seeds"])) != len(env["seeds"])
    ):
        p.error("Environment seeds must be distinct unsigned 64-bit integers.")
    for kind, keys in (
        ("fixture", ("fixture",)),
        ("case", ("fixture", "heuristic", "seed", "passed")),
        ("self_check", ("name", "passed")),
    ):
        if any(any(k not in r for k in keys) for r in by[kind]):
            p.error(f"Incomplete {kind} record.")
    if any(type(r["passed"]) is not bool for r in cases + checks):
        p.error("Case and self-check verdicts must be JSON booleans.")
    fx = {f["fixture"]: f for f in by["fixture"]}
    failed = [c for c in cases if not c["passed"]]
    metric_keys = (
        "d2_after_swap_decomposition",
        "n2_after_swap_decomposition",
        "swaps_inserted",
        "output_depth",
    )
    if any(
        type(c.get(k)) is not int or c[k] < 0 for c in cases if c["passed"] for k in metric_keys
    ):
        p.error(
            "Successful cases must contain D2 and N2 after SWAP decomposition; "
            "rerun run_validation.py to regenerate the results."
        )
    fixtures = ("qft10", "random10x60", "adder4", "ring10", "qv10", "dtc10")
    expected = Counter(
        (f, h, s) for f in fixtures for s in env["seeds"] for h in ("decay", "wait_time")
    )
    complete = (
        len(by["environment"]) == 1
        and bool(env["seeds"])
        and env["heuristics"] == ["decay", "wait_time"]
        and env["coupling_map"] == "line(10)"
        and env["trials"] == 1
        and Counter(f["fixture"] for f in by["fixture"]) == Counter(fixtures)
        and Counter((c["fixture"], c["heuristic"], c["seed"]) for c in cases) == expected
        and Counter(c["name"] for c in checks)
        == Counter(("ignoring_final_layout_must_fail", "extra_x_gate_must_fail"))
    )
    consistent = all(
        c.get("operator_equal") is True
        and c.get("width_ok") is True
        and c.get("layout_present") is True
        and c.get("connectivity_violations") == 0
        and isinstance(c.get("final_permutation"), list)
        and sorted(c["final_permutation"]) == list(range(10))
        for c in cases
        if c["passed"]
    ) and not any(r.get("error") for r in cases + checks + by["fixture"])
    ok = complete and consistent and not failed and all(c["passed"] for c in checks)
    L = [
        "# SABRE wait-time heuristic: routing correctness check",
        "",
        f"- Revision `{env['sha']}`; build `{env['accelerate_file']}`; qiskit {env['qiskit_version']}, "
        f"Python {env['python']}, {env['platform']}",
        f"- Run {env['timestamp']}; seeds {env['seeds']}; coupling map {env['coupling_map']}; "
        f"trials {env['trials']}; trivial initial layout; heuristics {list(env['heuristics'])}",
        "- Check per case: `Operator.from_circuit(out) == Operator.from_circuit(qc)` (layout-aware, "
        "global phase kept) and every two-qubit gate on a coupling edge",
        "",
        f"## Result: {'PASS' if ok else 'FAIL'} — {len(cases) - len(failed)}/{len(cases)} cases, "
        f"{sum(c['passed'] for c in checks)}/{len(checks)} self-checks",
        "",
    ]
    if not complete:
        L += [
            "Incomplete or duplicate results: expected all six fixtures, every requested seed "
            "under both heuristics, and both named self-checks, exactly once per combination.",
            "",
        ]
    if not consistent:
        L += [
            "Inconsistent results: a successful case lacks passing correctness evidence, "
            "or a fixture/case/self-check contains an error.",
            "",
        ]
    if failed:
        L += [
            "### Failed cases",
            table(
                [
                    "fixture",
                    "heuristic",
                    "seed",
                    "operator_equal",
                    "connectivity_violations",
                    "error",
                ],
                [
                    [
                        c["fixture"],
                        c["heuristic"],
                        c["seed"],
                        c.get("operator_equal"),
                        c.get("connectivity_violations"),
                        c.get("error", ""),
                    ]
                    for c in failed
                ],
            ),
            "",
        ]
    L += [
        "## Per-fixture results",
        table(
            [
                "fixture",
                "input ops",
                "input depth",
                "heuristic",
                "seed",
                "swaps",
                "depth before decomp",
                "D2 after SWAP decomp",
                "N2 after SWAP decomp",
                "final perm changed",
                "pass",
            ],
            [
                [
                    c["fixture"],
                    fx.get(c["fixture"], {}).get("input_ops"),
                    fx.get(c["fixture"], {}).get("input_depth"),
                    c["heuristic"],
                    c["seed"],
                    c.get("swaps_inserted"),
                    c.get("output_depth"),
                    c.get("d2_after_swap_decomposition"),
                    c.get("n2_after_swap_decomposition"),
                    c.get("final_permutation_changed"),
                    "yes" if c["passed"] else "NO",
                ]
                for c in cases
            ],
        ),
        "",
    ]
    pairs = defaultdict(dict)
    for c in cases:
        pairs[(c["fixture"], c["seed"])][c["heuristic"]] = c
    rows = []
    metric_rows = []
    for (f, s), d in sorted(pairs.items()):
        if (
            {"decay", "wait_time"} <= d.keys()
            and d["decay"]["passed"]
            and d["wait_time"]["passed"]
            and all(
                expected[(f, h, s)] == 1
                and sum(c["fixture"] == f and c["heuristic"] == h and c["seed"] == s for c in cases)
                == 1
                for h in ("decay", "wait_time")
            )
        ):
            sd, sw = d["decay"]["swaps_inserted"], d["wait_time"]["swaps_inserted"]
            dd, dw = d["decay"]["output_depth"], d["wait_time"]["output_depth"]
            rows.append([f, s, sd, sw, sw - sd, dd, dw, dw - dd])
            d2_off, d2_on = (d[h]["d2_after_swap_decomposition"] for h in ("decay", "wait_time"))
            n2_off, n2_on = (d[h]["n2_after_swap_decomposition"] for h in ("decay", "wait_time"))
            metric_rows.append([f, s, d2_off, d2_on, d2_on - d2_off, n2_off, n2_on, n2_on - n2_off])
    L += [
        "## decay vs wait_time on the same build (informational, not pass/fail)",
        "Off = decay; on = wait_time. D2 is two-qubit depth and N2 is two-qubit gate count, "
        "both measured after expanding every SWAP into three CX gates. Directives are excluded. "
        "Other gates retain their existing definitions and no optimization follows decomposition. "
        "Differences are on - off; negative means improvement.",
        "",
        table(["fixture", "seed", "D2 off", "D2 on", "ΔD2", "N2 off", "N2 on", "ΔN2"], metric_rows),
        "",
        "### SWAP count and original routed depth (before decomposition)",
        f"SWAPs with wait_time: fewer in {sum(r[4] < 0 for r in rows)}, equal in "
        f"{sum(r[4] == 0 for r in rows)}, more in {sum(r[4] > 0 for r in rows)} of {len(rows)} pairs.",
        "",
        table(
            [
                "fixture",
                "seed",
                "swaps decay",
                "swaps wait_time",
                "Δ swaps",
                "depth decay",
                "depth wait_time",
                "Δ depth",
            ],
            rows,
        ),
        "",
        "## Self-checks",
        table(
            ["check", "fixture", "heuristic", "seed", "passed", "error"],
            [
                [
                    c["name"],
                    c.get("fixture"),
                    c.get("heuristic"),
                    c.get("seed"),
                    c["passed"],
                    c.get("error", ""),
                ]
                for c in checks
            ],
        ),
        "",
        "## Limitations",
        "- Six circuits, 10 qubits, one bidirectional line, trivial initial layout, `SabreSwap` only "
        "(no `SabreLayout`, no full `transpile`).",
        "- One build: this compares the heuristic on and off on the same revision; it does not compare "
        "against the pre-feature revision.",
        "- D2 and N2 expand SWAPs only; other two-qubit operations (including unitary gates) "
        "remain one operation each. These are not metrics after full native-basis translation.",
        "- D2/N2, swap and depth columns are routing-quality observations, not timings.",
    ]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
