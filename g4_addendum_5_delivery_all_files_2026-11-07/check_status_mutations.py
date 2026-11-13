#!/usr/bin/env python3
"""Mutation test of the status handling of check_addendum4.py (v1) and check_addendum4_v2.py.
Copies the delivered Addendum 4 into a scratch directory, injects status text, runs both checkers on each mutant.
Read-only with respect to the repository; the checkers do read-only git calls."""
import sys, os, re, subprocess
S = "/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad"; F = f"{S}/deliver_a5/final6"
ADD = f"{F}/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_4_THIRD_ATTACHED_REVIEW_AND_P1d_REV3_2026-11-06.md"
W = f"{S}/a7/mut"; os.makedirs(W, exist_ok=True)
base = open(ADD, encoding="utf-8").read()
GOV = "**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
WANT = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
def inject_after_governing(line): return base.replace(GOV, GOV + "\n\n" + line, 1) if False else base.replace("\nLabels: **[OBSERVED]**", "\n" + line + "\n\nLabels: **[OBSERVED]**", 1)
M = {
 "M0 control: unchanged": base,
 "M1 sentence 'G4 is now CLOSED.'": inject_after_governing("Update: G4 is now CLOSED."),
 "M2 second, conflicting governing line": inject_after_governing("**Governing statuses, unchanged:** G4 CLOSED · High · freeze-blocking. G5–G8 RELEASED. Freeze readiness DECLARED."),
 "M3 last line replaced by a conflicting sentence": base.rstrip("\n").rsplit("\n", 1)[0] + "\nG4 CLOSED · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.\n",
 "M4 governing line duplicated exactly": base.replace(GOV, GOV + "\n\n" + GOV, 1),
 "M5 sentence 'Freeze readiness DECLARED.'": inject_after_governing("Freeze readiness DECLARED."),
 "M6 ambiguous 'G4 OPEN or CLOSED, pending a decision.'": inject_after_governing("G4 OPEN or CLOSED, pending a decision."),
 "M7 gate status word 'PARTIAL'": base.replace("| **PASS** | I60, I61, I59 |", "| **PARTIAL** | I60, I61, I59 |", 1),
 "M8 sentence 'G5–G8 RELEASED.'": inject_after_governing("G5–G8 RELEASED."),
 "M9 sentence 'Implementation is authorized.'": inject_after_governing("Implementation is authorized."),
}
for n, t in M.items():
    if n.startswith("M7"): assert "PARTIAL" in t, "M7 did not apply"
    if n.startswith("M3"): assert t != base
ARGS = [f"{F}/g4_attachment_af046c14_p1d_rev3_block_tests_evidence_I51-I64.zip", f"{F}/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch",
        f"{S}/a5/proposed_diffs/P1d_rev2_handoff_section7_18_verification_block_PROPOSED.patch",
        "/mnt/user-data/attachments/d441201d-0373-573d-8f64-186072f858d3/af046c14-attachment.txt",
        f"{S}/deliver_a5/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_1_P1_PUSHED_2026-11-01.md",
        f"{S}/deliver_a5/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_2_ATTACHED_REVIEW_AND_P1d_2026-11-02.md",
        f"{S}/deliver_a5/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_3_SECOND_ATTACHED_REVIEW_AND_P1d_REV2_2026-11-02.md",
        f"{S}/deliver_a5/CONSOLIDATED_EVIDENCE_REPORT_P1_P2_P3_EXECUTION_2026-11-01.md"]
def run(checker, path):
    r = subprocess.run(["python3", "-I", checker, path, f"{S}/a5/evidence", "/home/claude/ocbrain-v4.1", *ARGS], capture_output=True, text=True, timeout=120)
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    return ("ACCEPTED" if r.returncode == 0 else "REJECTED"), (fails[0][:100] if fails else "")
print(f"{'mutant':52s} {'v1':9s} {'v2':9s}  first v2 FAIL line")
tally = {"v1": 0, "v2": 0}
for i, (n, t) in enumerate(M.items()):
    p = f"{W}/m{i}.md"; open(p, "w", encoding="utf-8").write(t)
    a, _ = run(f"{S}/a6_scripts/check_addendum4.py", p); b, f2 = run(f"{S}/a6_scripts/check_addendum4_v2.py", p)
    want_reject = not n.startswith("M0")
    if want_reject:
        tally["v1"] += a == "REJECTED"; tally["v2"] += b == "REJECTED"
    flag = lambda x: "" if (x == "REJECTED") == want_reject else " *"
    print(f"{n:52s} {a+flag(a):9s} {b+flag(b):9s}  {f2}")
print(f"mutants that must be rejected: 9; rejected by v1: {tally['v1']}; rejected by v2: {tally['v2']}   [* = wrong outcome]")
