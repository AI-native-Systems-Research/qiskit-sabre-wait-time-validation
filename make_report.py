#!/usr/bin/env python
"""Write a short correctness report using only the standard library."""
import argparse
import json
from collections import Counter
from pathlib import Path

from run_validation import CHECKS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results/results.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("report.md"))
    args = parser.parse_args()
    records = [json.loads(line) for line in args.results.read_text().splitlines() if line.strip()]
    environments = [r for r in records if r["record"] == "environment"]
    if len(environments) != 1:
        parser.error("Expected exactly one environment record")
    env = environments[0]
    cases = [r for r in records if r["record"] == "case"]
    checks = [r for r in records if r["record"] == "self_check"]
    expected = Counter((f, s) for f in env["fixtures"] for s in env["seeds"])
    complete = (
        len(env["fixtures"]) == len(set(env["fixtures"])) == 16
        and bool(env["seeds"]) and len(env["seeds"]) == len(set(env["seeds"]))
        and env["heuristic"] == "wait_time" and env["coupling_map"] == "line(10)" and env["trials"] == 1
        and len(records) == 1 + len(cases) + len(checks)
        and Counter((r["fixture"], r["seed"]) for r in cases) == expected
        and Counter(r["name"] for r in checks) == Counter(CHECKS)
    )
    failed = [r for r in cases + checks if r.get("passed") is not True or r.get("error")]
    ok = complete and not failed
    lines = [
        "# SABRE wait-time correctness", "",
        f"**{'PASS' if ok else 'FAIL'}** — {sum(r.get('passed') is True for r in cases)}/{sum(expected.values())} "
        f"cases; {sum(r.get('passed') is True for r in checks)}/2 self-checks.", "",
        f"Revision: `{env['sha']}`. Seeds: `{env['seeds']}`.",
        f"Run: {env['timestamp']}. Qiskit {env['qiskit_version']}; Python {env['python']}.", "",
        "16 circuits, 10 qubits each; bidirectional line, trivial layout, one routing trial.",
        "Each output must match its original unitary (layout-aware, global phase kept, default "
        "tolerances), preserve width and layout metadata, and satisfy connectivity.", "",
        "| Circuit | Passed |", "|---|---|",
    ]
    for fixture in env["fixtures"]:
        passed = sum(r.get("passed") is True for r in cases if r["fixture"] == fixture)
        lines.append(f"| {fixture} | {passed}/{len(env['seeds'])} |")
    sample = next((r for r in checks if "fixture" in r), None)
    source = f"`{sample['fixture']}` seed {sample['seed']}" if sample else "a passing case"
    lines += [
        "", "Self-checks:", "",
        "Negative controls showing the unitary comparison can fail. Each takes a passing "
        f"routed circuit whose final permutation is not the identity ({source}), breaks it "
        "on purpose, and passes only if the result no longer matches the reference.", "",
    ]
    labels = (
        ("Ignored layout detected", "build the unitary with `ignore_set_layout=True`, "
         "so the SWAP permutation is not undone"),
        ("Extra X gate detected", "append an X gate on physical qubit 0, keeping the layout"),
    )
    for name, (label, detail) in zip(CHECKS, labels):
        matches = [r for r in checks if r["name"] == name]
        passed = len(matches) == 1 and matches[0].get("passed") is True and not matches[0].get("error")
        lines.append(f"- {label}: {'PASS' if passed else 'FAIL'} — {detail}.")
    if not complete:
        lines += ["", "FAIL: missing, duplicate, or unexpected results/settings."]
    for rec in failed:
        label = f"{rec['fixture']} seed {rec['seed']}" if rec["record"] == "case" else rec["name"]
        lines += ["", f"FAIL: {label}: {rec.get('error', 'check failed')}"]
    lines += ["", "Scope: routing-only checks on these circuits and seeds, not a general proof. "
              "Raw results and build path: `results/results.jsonl`."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{'PASS' if ok else 'FAIL'}; wrote {args.out}")
    return int(not ok)


if __name__ == "__main__":
    raise SystemExit(main())
