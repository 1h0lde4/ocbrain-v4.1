#!/usr/bin/env python3
"""Re-derive the AZ1 results from the recorded verbose outputs. Run from the repo root:
   python3 docs/reviews/q4b-independent-review/artifacts/ME_AZ1_SIX_FILE_RUN_2026-11-24/verify/summarize_az1.py
Reads run/*.txt only; no network, no execution of repository code. Exits 1 if any check fails or the check count is not exactly 24."""
import collections, pathlib, re, sys
PKG = pathlib.Path(__file__).resolve().parent.parent
EXPECT = {"tests/test_execution_runtime.py": 37, "tests/test_supervisor_worker.py": 29, "tests/test_evaluator_worker.py": 26,
          "tests/test_workflow_runtime.py": 35, "tests/test_workflow_failure_disclosure.py": 8, "tests/test_scheduler_failure_containment.py": 35}
SHAS = {"4a4783c": "4a4783c47ac37971a7d51ab3d7ab6fc904a37106", "f13bfde": "f13bfdefcdd197ed1f966de0b1f93037a4168af4"}
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
for short, sha in SHAS.items():
    t = (PKG / "run" / f"az1_{short}.txt").read_text(encoding="utf-8", errors="replace")
    print(f"\n== {short}: {t.splitlines()[1]}")
    check(f"{short}: header names the full commit SHA", sha in t.splitlines()[0])
    c = collections.defaultdict(collections.Counter)
    for m in re.finditer(r"^(tests/\S+?\.py)::\S+ (PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)", t, re.M): c[m.group(1)][m.group(2)] += 1
    for f, n in EXPECT.items(): check(f"{short}: {f} has {n} PASSED and nothing else", dict(c[f]) == {"PASSED": n}, str(dict(c[f])))
    tot = collections.Counter(); [tot.update(v) for v in c.values()]
    check(f"{short}: total is 170 PASSED with no other outcome", dict(tot) == {"PASSED": 170}, str(dict(tot)))
    check(f"{short}: pytest summary line says 170 passed", re.search(r"=+ 170 passed in [\d.]+s =+", t) is not None)
    check(f"{short}: exit status 0 recorded", "# exit status: 0" in t)
    check(f"{short}: test_a_successful_workflow_run_is_unchanged PASSED", re.search(r"test_a_successful_workflow_run_is_unchanged PASSED", t) is not None)
n = len(results); print(f"\nchecks run: {n}; passed: {sum(results)}; failed: {n - sum(results)}")
assert n == 22, f"expected exactly 22 checks, ran {n}"
sys.exit(0 if all(results) else 1)
